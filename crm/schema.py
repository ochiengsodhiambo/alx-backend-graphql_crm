import re
from decimal import Decimal
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from .models import Customer, Product, Order
from .filters import CustomerFilter, ProductFilter, OrderFilter


# -----------------------------
# Shared Error Type
# -----------------------------
class FieldError(graphene.ObjectType):
    field = graphene.String()
    message = graphene.String()


# -----------------------------
# GraphQL Types
# -----------------------------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = "__all__"
        interfaces = (relay.Node,)
        filterset_class = CustomerFilter


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = "__all__"
        interfaces = (relay.Node,)
        filterset_class = ProductFilter


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = "__all__"
        interfaces = (relay.Node,)
        filterset_class = OrderFilter


# -----------------------------
# Validation Helper
# -----------------------------
def validate_phone(phone: str) -> bool:
    if not phone:
        return True
    patterns = [
        re.compile(r"^\+\d{7,15}$"),  # +1234567890
        re.compile(r"^\d{3}-\d{3}-\d{4}$"),  # 123-456-7890
        re.compile(r"^\d{7,15}$"),  # digits only
    ]
    return any(p.match(phone) for p in patterns)


# -----------------------------
# Mutations
# -----------------------------
class CreateCustomer(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String()

    customer = graphene.Field(CustomerType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = graphene.List(FieldError)

    @classmethod
    def mutate(cls, root, info, name, email, phone=None):
        errors = []
        try:
            validate_email(email)
        except ValidationError:
            errors.append(FieldError(field="email", message="Invalid email format."))

        if Customer.objects.filter(email__iexact=email).exists():
            errors.append(FieldError(field="email", message="Email already exists."))

        if phone and not validate_phone(phone):
            errors.append(FieldError(field="phone", message="Invalid phone format."))

        if errors:
            return cls(success=False, message="Validation errors", errors=errors)

        customer = Customer.objects.create(name=name.strip(), email=email.strip(), phone=phone)
        return cls(customer=customer, success=True, message="Customer created successfully", errors=[])


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        customers = graphene.List(graphene.InputObjectType(
            name="CustomerInput",
            fields={
                "name": graphene.String(required=True),
                "email": graphene.String(required=True),
                "phone": graphene.String()
            }
        ), required=True)

    created_customers = graphene.List(CustomerType)
    errors = graphene.List(FieldError)
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, customers):
        created, errors = [], []
        for index, c in enumerate(customers):
            name, email, phone = c["name"], c["email"], c.get("phone")
            try:
                validate_email(email)
            except ValidationError:
                errors.append(FieldError(field=f"customers[{index}].email", message="Invalid email format."))
                continue

            if Customer.objects.filter(email__iexact=email).exists():
                errors.append(FieldError(field=f"customers[{index}].email", message="Email already exists."))
                continue

            if phone and not validate_phone(phone):
                errors.append(FieldError(field=f"customers[{index}].phone", message="Invalid phone format."))
                continue

            try:
                with transaction.atomic():
                    cust = Customer.objects.create(name=name.strip(), email=email.strip(), phone=phone)
                    created.append(cust)
            except Exception as e:
                errors.append(FieldError(field=f"customers[{index}]", message=str(e)))

        success = not errors
        msg = "All customers created successfully." if success else f"Created {len(created)}; {len(errors)} failed."
        return cls(created_customers=created, errors=errors, success=success, message=msg)


class CreateProduct(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Float(required=True)
        stock = graphene.Int(default_value=0)

    product = graphene.Field(ProductType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = graphene.List(FieldError)

    @classmethod
    def mutate(cls, root, info, name, price, stock=0):
        errors = []
        if not name.strip():
            errors.append(FieldError(field="name", message="Name cannot be empty."))
        if price <= 0:
            errors.append(FieldError(field="price", message="Price must be positive."))
        if stock < 0:
            errors.append(FieldError(field="stock", message="Stock cannot be negative."))
        if errors:
            return cls(success=False, message="Validation errors", errors=errors)

        product = Product.objects.create(name=name.strip(), price=Decimal(price), stock=stock)
        return cls(product=product, success=True, message="Product created successfully", errors=[])


class CreateOrder(graphene.Mutation):
    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.ID, required=True)
        order_date = graphene.DateTime()

    order = graphene.Field(OrderType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = graphene.List(FieldError)

    @classmethod
    def mutate(cls, root, info, customer_id, product_ids, order_date=None):
        errors = []
        try:
            customer = Customer.objects.get(id=customer_id)
        except ObjectDoesNotExist:
            errors.append(FieldError(field="customer_id", message="Invalid customer ID."))

        valid_products = Product.objects.filter(id__in=product_ids)
        if not valid_products:
            errors.append(FieldError(field="product_ids", message="No valid products found."))

        if errors:
            return cls(success=False, message="Validation errors", errors=errors)

        with transaction.atomic():
            order = Order.objects.create(
                customer=customer,
                order_date=order_date or timezone.now(),
                total_amount=sum(p.price for p in valid_products)
            )
            order.products.set(valid_products)
        return cls(order=order, success=True, message="Order created successfully", errors=[])


class UpdateLowStockProducts(graphene.Mutation):
    success = graphene.Boolean()
    message = graphene.String()
    updated_products = graphene.List(ProductType)

    @classmethod
    def mutate(cls, root, info):
        threshold = 10
        updated_products = []
        low_stock_products = Product.objects.filter(stock__lt=threshold)
        for p in low_stock_products:
            p.stock = threshold
            p.save()
            updated_products.append(p)
        msg = f"{len(updated_products)} products updated to stock {threshold}."
        return cls(success=True, message=msg, updated_products=updated_products)


# -----------------------------
# Queries
# -----------------------------
class Query(graphene.ObjectType):
    all_customers = DjangoFilterConnectionField(CustomerType, order_by=graphene.String())
    all_products = DjangoFilterConnectionField(ProductType, order_by=graphene.String())
    all_orders = DjangoFilterConnectionField(OrderType, order_by=graphene.String())
    node = relay.Node.Field()

    def resolve_all_customers(self, info, order_by=None, **kwargs):
        qs = Customer.objects.all()
        if order_by:
            qs = qs.order_by(order_by)
        return qs

    def resolve_all_products(self, info, order_by=None, **kwargs):
        qs = Product.objects.all()
        if order_by:
            qs = qs.order_by(order_by)
        return qs

    def resolve_all_orders(self, info, order_by=None, **kwargs):
        qs = Order.objects.all()
        if order_by:
            qs = qs.order_by(order_by)
        return qs


# -----------------------------
# Root Schema
# -----------------------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()
    update_low_stock_products = UpdateLowStockProducts.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)

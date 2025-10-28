import re
from decimal import Decimal
from graphene import relay
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from crm.models import Customer, Product, Order
from crm.filters import CustomerFilter, ProductFilter, OrderFilter

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
# Shared Error Type
# -----------------------------
class FieldError(graphene.ObjectType):
    field = graphene.String()
    message = graphene.String()


# -----------------------------
# Input for Bulk Creation
# -----------------------------
class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()


# -----------------------------
# Validation Helpers
# -----------------------------
def validate_phone(phone: str) -> bool:
    """Validate common phone number formats."""
    if not phone:
        return True
    patterns = [
        re.compile(r"^\+\d{7,15}$"),  # +1234567890
        re.compile(r"^\d{3}-\d{3}-\d{4}$"),  # 123-456-7890
        re.compile(r"^\d{7,15}$"),  # plain digits
    ]
    return any(p.match(phone) for p in patterns)


# -----------------------------
# Mutations
# -----------------------------
class CreateCustomer(graphene.Mutation):
    """Create a single customer."""
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

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            errors.append(FieldError(field="email", message="Invalid email format."))

        # Check unique email
        if Customer.objects.filter(email__iexact=email).exists():
            errors.append(FieldError(field="email", message="Email already exists."))

        # Validate phone format
        if phone and not validate_phone(phone):
            errors.append(FieldError(field="phone", message="Invalid phone format. Use +1234567890 or 123-456-7890."))

        if errors:
            return CreateCustomer(success=False, message="Validation errors", errors=errors)

        customer = Customer.objects.create(name=name.strip(), email=email.strip(), phone=phone)
        return CreateCustomer(customer=customer, success=True, message="Customer created successfully", errors=[])


class BulkCreateCustomers(graphene.Mutation):
    """Bulk create customers (partial success allowed)."""
    class Arguments:
        customers = graphene.List(CustomerInput, required=True)

    created_customers = graphene.List(CustomerType)
    errors = graphene.List(FieldError)
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, customers):
        created, errors = [], []

        for index, c in enumerate(customers):
            name, email, phone = c.name.strip(), c.email.strip(), c.phone
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
                    cust = Customer.objects.create(name=name, email=email, phone=phone)
                    created.append(cust)
            except Exception as e:
                errors.append(FieldError(field=f"customers[{index}]", message=f"Error: {str(e)}"))

        success = len(errors) == 0
        msg = (
            "All customers created successfully."
            if success
            else f"Created {len(created)} customers; {len(errors)} failed."
        )
        return BulkCreateCustomers(created_customers=created, errors=errors, success=success, message=msg)


class CreateProduct(graphene.Mutation):
    """Create a product."""
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
            return CreateProduct(success=False, message="Validation errors", errors=errors)

        product = Product.objects.create(name=name.strip(), price=Decimal(price), stock=stock)
        return CreateProduct(product=product, success=True, message="Product created successfully", errors=[])


class CreateOrder(graphene.Mutation):
    """Create an order."""
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

        if not product_ids:
            errors.append(FieldError(field="product_ids", message="At least one product is required."))
        else:
            valid_products = list(Product.objects.filter(id__in=product_ids))
            if len(valid_products) != len(product_ids):
                invalid_ids = set(product_ids) - set(p.id for p in valid_products)
                errors.append(FieldError(field="product_ids", message=f"Invalid IDs: {', '.join(map(str, invalid_ids))}"))

        if errors:
            return CreateOrder(success=False, message="Validation errors", errors=errors)

        with transaction.atomic():
            order = Order.objects.create(
                customer=customer,
                order_date=order_date or timezone.now(),
                total_amount=Decimal("0.00"),
            )
            order.products.set(valid_products)
            total_amount = sum(p.price for p in valid_products)
            order.total_amount = total_amount
            order.save()

        return CreateOrder(order=order, success=True, message="Order created successfully", errors=[])


class UpdateLowStockProducts(graphene.Mutation):
    """Restock low-stock products (< 10 by default)."""
    class Arguments:
        threshold = graphene.Int(required=False, default_value=10)
        restock_amount = graphene.Int(required=False, default_value=50)

    updated_count = graphene.Int()

    def mutate(self, info, threshold, restock_amount):
        low_stock_products = Product.objects.filter(stock__lt=threshold)
        updated_count = low_stock_products.count()
        for p in low_stock_products:
            p.stock += restock_amount
            p.save()
        return UpdateLowStockProducts(updated_count=updated_count)


# -----------------------------
# Query and Mutation Root
# -----------------------------
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    all_customers = DjangoFilterConnectionField(CustomerType, order_by=graphene.String())
    all_products = DjangoFilterConnectionField(ProductType, order_by=graphene.String())
    all_orders = DjangoFilterConnectionField(OrderType, order_by=graphene.String())

    def resolve_all_customers(self, info, order_by=None, **kwargs):
        qs = Customer.objects.all()
        return qs.order_by(order_by) if order_by else qs

    def resolve_all_products(self, info, order_by=None, **kwargs):
        qs = Product.objects.all()
        return qs.order_by(order_by) if order_by else qs

    def resolve_all_orders(self, info, order_by=None, **kwargs):
        qs = Order.objects.all()
        return qs.order_by(order_by) if order_by else qs


class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()
    update_low_stock_products = UpdateLowStockProducts.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)

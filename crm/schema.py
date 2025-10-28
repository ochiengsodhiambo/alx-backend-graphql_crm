import graphene
from .models import Customer, Product, Order
from datetime import datetime


class ProductType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    stock = graphene.Int()
    price = graphene.Float()


class UpdateLowStockProducts(graphene.Mutation):
    """Mutation to restock products with low stock (< 10)."""

    class Arguments:
        threshold = graphene.Int(required=False, default_value=10)
        restock_amount = graphene.Int(required=False, default_value=50)

    updated_count = graphene.Int()

    def mutate(self, info, threshold, restock_amount):
        low_stock_products = Product.objects.filter(stock__lt=threshold)
        updated_count = low_stock_products.count()
        for product in low_stock_products:
            product.stock += restock_amount
            product.save()
        return UpdateLowStockProducts(updated_count=updated_count)


class Mutation(graphene.ObjectType):
    update_low_stock_products = UpdateLowStockProducts.Field()


class Query(graphene.ObjectType):
    hello = graphene.String()

    def resolve_hello(root, info):
        return f"Hello, GraphQL! Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


schema = graphene.Schema(query=Query, mutation=Mutation)

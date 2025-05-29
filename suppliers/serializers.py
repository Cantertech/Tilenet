
from rest_framework import serializers
from .models import Supplier, SupplierProduct, Order, OrderItem, SupplierReview

class SupplierProductSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    
    class Meta:
        model = SupplierProduct
        fields = '__all__'

class SupplierSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = '__all__'
    
    def get_products_count(self, obj):
        return obj.products.count()

class SupplierDetailSerializer(serializers.ModelSerializer):
    products = SupplierProductSerializer(many=True, read_only=True)
    
    class Meta:
        model = Supplier
        fields = '__all__'

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'quantity', 'unit_price', 'total_price')
        read_only_fields = ('total_price',)

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ('user', 'subtotal', 'total', 'status', 'created_at', 'updated_at')
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Calculate subtotal and total
        subtotal = 0
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            unit_price = product.price
            subtotal += quantity * unit_price
        
        delivery_fee = validated_data.get('delivery_fee', 0)
        total = subtotal + delivery_fee
        
        # Create order
        validated_data['user'] = self.context['request'].user
        validated_data['subtotal'] = subtotal
        validated_data['total'] = total
        
        order = Order.objects.create(**validated_data)
        
        # Create order items
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            unit_price = product.price
            total_price = quantity * unit_price
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
        
        return order

class SupplierReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = SupplierReview
        fields = '__all__'
        read_only_fields = ('user', 'created_at')
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

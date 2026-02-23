from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError


class Sucursal(models.Model):
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=250)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sucursal"
        verbose_name_plural = "Sucursales"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)

    # IDENTIFICACIÓN
    codigo = models.CharField(max_length=50, unique=True)
    tipo_registro = models.CharField(max_length=50, blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)

    # INFORMACIÓN PRINCIPAL
    nombre = models.CharField(max_length=200)
    forma_farmaceutica = models.CharField(max_length=100, blank=True, null=True)
    concentracion = models.CharField(max_length=100, blank=True, null=True)
    presentacion = models.CharField(max_length=100, blank=True, null=True)
    unidades_por_presentacion = models.IntegerField(default=1)

    descripcion = models.TextField(blank=True, null=True)

    # CONTROL FARMACÉUTICO
    proveedor = models.CharField(max_length=200, blank=True, null=True)
    lote = models.CharField(max_length=100, blank=True, null=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)

    # PRECIOS
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_venta_menor = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta_mayor = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class StockSucursal(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    stock = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)

    class Meta:
        unique_together = ('producto', 'sucursal')
        verbose_name = "Stock por Sucursal"
        verbose_name_plural = "Stock por Sucursal"

    def __str__(self):
        return f"{self.producto.nombre} - {self.sucursal.nombre}"

    def stock_bajo(self):
        return self.stock <= self.stock_minimo


class Entrada(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Entrada"
        verbose_name_plural = "Entradas"

    def __str__(self):
        return f"Entrada - {self.producto.nombre} ({self.cantidad})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        stock_obj, created = StockSucursal.objects.get_or_create(
            producto=self.producto,
            sucursal=self.sucursal
        )

        stock_obj.stock += self.cantidad
        stock_obj.save()


class Venta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    ganancia = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    def __str__(self):
        return f"Venta - {self.producto.nombre} ({self.cantidad})"

    # ✅ VALIDACIÓN PROFESIONAL
    def clean(self):
        stock_obj, created = StockSucursal.objects.get_or_create(
            producto=self.producto,
            sucursal=self.sucursal
        )

        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a 0.")

        if self.cantidad > stock_obj.stock:
            raise ValidationError(
                f"No hay suficiente stock. Disponible: {stock_obj.stock}"
            )

    # ✅ GUARDADO CON GANANCIA AUTOMÁTICA
    def save(self, *args, **kwargs):
        self.full_clean()

        stock_obj = StockSucursal.objects.get(
            producto=self.producto,
            sucursal=self.sucursal
        )

        # Calcular total
        self.total = self.cantidad * self.precio_unitario

        # Calcular ganancia
        costo_total = self.cantidad * self.producto.precio_compra
        self.ganancia = self.total - costo_total

        super().save(*args, **kwargs)

        # Descontar stock
        stock_obj.stock -= self.cantidad
        stock_obj.save()
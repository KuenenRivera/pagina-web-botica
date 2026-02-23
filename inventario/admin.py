from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import openpyxl

from .models import Sucursal, Producto, StockSucursal, Entrada, Venta


# ===============================
# SUCURSAL
# ===============================
@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "direccion", "activo", "fecha_creacion")
    list_filter = ("activo",)
    search_fields = ("nombre", "direccion")


# ===============================
# PRODUCTO
# ===============================
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "sucursal",
        "categoria",
        "precio_venta_menor",
        "activo",
    )
    list_filter = ("activo", "sucursal", "categoria")
    search_fields = ("codigo", "nombre")
    ordering = ("nombre",)


# ===============================
# STOCK POR SUCURSAL
# ===============================
@admin.register(StockSucursal)
class StockSucursalAdmin(admin.ModelAdmin):
    list_display = (
        "producto",
        "sucursal",
        "stock_coloreado",
        "stock_minimo",
        "estado_stock",
    )
    list_filter = ("sucursal",)
    search_fields = ("producto__nombre",)

    # ✅ Acciones (Botón de reponer)
    actions = ["reponer_stock"]

    def reponer_stock(self, request, queryset):
        for stock in queryset:
            stock.stock = stock.stock_minimo + 10
            stock.save()
        self.message_user(request, "Stock repuesto automáticamente ✅")

    reponer_stock.short_description = "📦 Reponer automáticamente"

    # 🔴 Stock coloreado
    def stock_coloreado(self, obj):
        if obj.stock <= obj.stock_minimo:
            return format_html(
                '<span style="color:red;font-weight:bold;">{}</span>',
                obj.stock
            )
        return obj.stock

    stock_coloreado.short_description = "Stock"

    # ✅ Estado visual (aquí estaba tu error)
    # format_html SIEMPRE debe tener {} o al menos args
    def estado_stock(self, obj):
        if obj.stock <= obj.stock_minimo:
            return format_html(
                '<span style="color:red;font-weight:bold;">{}</span>',
                "⚠ Stock Bajo"
            )
        return format_html(
            '<span style="color:green;font-weight:bold;">{}</span>',
            "✔ Normal"
        )

    estado_stock.short_description = "Estado"

    # ✅ contador banner
    def changelist_view(self, request, extra_context=None):
        productos_bajo = StockSucursal.objects.filter(
            stock__lte=F("stock_minimo")
        ).count()

        extra_context = extra_context or {}
        extra_context["productos_bajo"] = productos_bajo

        return super().changelist_view(request, extra_context=extra_context)


# ===============================
# ENTRADAS
# ===============================
@admin.register(Entrada)
class EntradaAdmin(admin.ModelAdmin):
    list_display = ("producto", "sucursal", "cantidad", "fecha", "usuario")
    list_filter = ("sucursal", "fecha")
    search_fields = ("producto__nombre",)
    ordering = ("-fecha",)


# ===============================
# VENTAS (DASHBOARD + GRÁFICO + TOP 5 + MES ANTERIOR + EXCEL)
# ===============================
@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "producto",
        "sucursal",
        "cantidad",
        "precio_unitario",
        "total",
        "ganancia",
        "fecha",
        "usuario",
    )

    list_filter = ("sucursal", "fecha")
    search_fields = ("producto__nombre",)
    ordering = ("-fecha",)

    actions = ["exportar_excel"]

    def exportar_excel(self, request, queryset):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Ventas"

        sheet.append(["Producto", "Sucursal", "Cantidad", "Precio Unit", "Total", "Ganancia", "Fecha"])

        for venta in queryset:
            sheet.append([
                venta.producto.nombre,
                venta.sucursal.nombre,
                venta.cantidad,
                float(venta.precio_unitario),
                float(venta.total),
                float(venta.ganancia),
                venta.fecha.strftime("%d/%m/%Y %H:%M"),
            ])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=ventas.xlsx"
        workbook.save(response)
        return response

    exportar_excel.short_description = "📄 Exportar a Excel"

    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()
        now = timezone.now()

        ventas = Venta.objects.all()

        # ===== DASHBOARD HOY / MES =====
        ventas_hoy = ventas.filter(fecha__date=today)
        ventas_mes = ventas.filter(fecha__year=now.year, fecha__month=now.month)

        total_hoy = ventas_hoy.aggregate(Sum("total"))["total__sum"] or 0
        total_mes = ventas_mes.aggregate(Sum("total"))["total__sum"] or 0

        ganancia_hoy = ventas_hoy.aggregate(Sum("ganancia"))["ganancia__sum"] or 0
        ganancia_mes = ventas_mes.aggregate(Sum("ganancia"))["ganancia__sum"] or 0

        cantidad_hoy = ventas_hoy.count()

        # ===== MES ANTERIOR =====
        mes_anterior = (now.month - 1) or 12
        year_anterior = now.year if now.month != 1 else now.year - 1

        ventas_mes_anterior = ventas.filter(fecha__year=year_anterior, fecha__month=mes_anterior)
        total_mes_anterior = ventas_mes_anterior.aggregate(Sum("total"))["total__sum"] or 0

        # ===== GRÁFICO 7 DÍAS =====
        labels_7_dias = []
        data_7_dias = []

        for i in range(6, -1, -1):
            fecha = today - timedelta(days=i)
            total_dia = ventas.filter(fecha__date=fecha).aggregate(Sum("total"))["total__sum"] or 0
            labels_7_dias.append(fecha.strftime("%d/%m"))
            data_7_dias.append(float(total_dia))

        # ✅ IMPORTANTE para Chart.js: labels deben ser strings JSON válidos
        import json
        labels_7_dias_json = json.dumps(labels_7_dias)
        data_7_dias_json = json.dumps(data_7_dias)

        # ===== TOP 5 PRODUCTOS MÁS VENDIDOS =====
        top_productos = (
            Venta.objects
            .values("producto__nombre")
            .annotate(total_vendido=Sum("cantidad"))
            .order_by("-total_vendido")[:5]
        )

        extra_context = extra_context or {}
        extra_context.update({
            "total_hoy": total_hoy,
            "total_mes": total_mes,
            "total_mes_anterior": total_mes_anterior,
            "cantidad_hoy": cantidad_hoy,
            "ganancia_hoy": ganancia_hoy,
            "ganancia_mes": ganancia_mes,
            "labels_7_dias": labels_7_dias_json,
            "data_7_dias": data_7_dias_json,
            "top_productos": top_productos,
        })

        return super().changelist_view(request, extra_context=extra_context)
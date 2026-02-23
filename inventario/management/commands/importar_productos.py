import csv
from django.core.management.base import BaseCommand
from inventario.models import Producto, Sucursal
from datetime import datetime


class Command(BaseCommand):
    help = "Importar productos desde CSV"

    def add_arguments(self, parser):
        parser.add_argument("ruta_csv", type=str)

    def handle(self, *args, **kwargs):
        ruta = kwargs["ruta_csv"]

        with open(ruta, newline="", encoding="utf-8-sig") as archivo:
            reader = csv.DictReader(archivo, delimiter=";")

            print("COLUMNAS DETECTADAS:", reader.fieldnames)

            for fila in reader:
                try:
                    sucursal_nombre = (fila.get("sucursal") or "").strip()

                    if not sucursal_nombre:
                        self.stdout.write(self.style.ERROR("Fila sin sucursal"))
                        continue

                    # 🔥 AQUÍ ESTÁ EL CAMBIO IMPORTANTE
                    sucursal_obj = Sucursal.objects.filter(
                        nombre=sucursal_nombre
                    ).first()

                    if not sucursal_obj:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Sucursal no encontrada: {sucursal_nombre}"
                            )
                        )
                        continue

                    # ---- Manejo de fecha ----
                    fecha_venc = None
                    fecha_str = (fila.get("fecha_vencimiento") or "").strip()

                    if fecha_str:
                        try:
                            fecha_venc = datetime.strptime(
                                fecha_str, "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Fecha inválida en producto {fila.get('codigo')}"
                                )
                            )

                    Producto.objects.update_or_create(
                        codigo=fila.get("codigo"),
                        defaults={
                            "sucursal": sucursal_obj,
                            "tipo_registro": fila.get("tipo_registro"),
                            "categoria": fila.get("categoria"),
                            "nombre": fila.get("nombre"),
                            "forma_farmaceutica": fila.get("forma_farmaceutica"),
                            "concentracion": fila.get("concentracion"),
                            "presentacion": fila.get("presentacion"),
                            "unidades_por_presentacion": int(
                                fila.get("unidades_por_presentacion") or 1
                            ),
                            "descripcion": fila.get("descripcion"),
                            "proveedor": fila.get("proveedor"),
                            "lote": fila.get("lote"),
                            "precio_compra": float(
                                fila.get("precio_compra") or 0
                            ),
                            "precio_venta_menor": float(
                                fila.get("precio_venta_menor") or 0
                            ),
                            "precio_venta_mayor": float(
                                fila.get("precio_venta_mayor") or 0
                            ),
                            "stock": int(fila.get("stock") or 0),
                            "stock_minimo": int(
                                fila.get("stock_minimo") or 5
                            ),
                            "fecha_vencimiento": fecha_venc,
                            "activo": str(
                                fila.get("activo")
                            ).lower() in ["true", "1", "activo"],
                        },
                    )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error importando producto {fila.get('codigo')}: {e}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS("Importación finalizada correctamente"))
# WORKFLOW PROFESIONAL Y ORQUESTACIÓN PRINCIPAL
# =============================================================================
# RESUMEN DEL FLUJO PRINCIPAL (main):
# 1. Determina los archivos de entrada y salida SVG (por argumentos o por defecto).
# 2. Llama a la función principal de proceso (procesar_svg) que:
#    a) Carga el SVG de entrada y obtiene los valores originales de los <rect>.
#    b) Reescala todos los <rect> según la nueva proporción (pulgadas reales).
#    c) Alinea todas las piezas adyacentes usando lógica BFS, partiendo de la pieza más cercana a (0,0).
#    d) Guarda el SVG modificado en el archivo de salida.
#    e) Imprime información de trazabilidad y debug profesional (esquinas, adyacencias, etc.).
# 3. Toda la lógica de negocio, debug y análisis está encapsulada en funciones de proceso.
# 4. El bloque bajo if __name__ == "__main__" es el único punto de entrada y orquestación.
# =============================================================================
# NOTA DE USO Y MANTENIMIENTO (prompt reutilizable):
#
# Todas las modificaciones, análisis, debug, y lógica adicional deben implementarse
# exclusivamente dentro de las funciones de proceso (por ejemplo, listar_rects_adyacentes,
# get_rects_ordenados_por_orientacion_y_distancia, recalcular_rects, etc.), y nunca
# directamente en la función main.
#
# Si se requiere agregar o modificar lógica de debug, impresión de valores, análisis de
# adyacencias, o cualquier otro procesamiento, debe hacerse encapsulando esa lógica en las
# funciones de proceso correspondientes, de modo que main solo orqueste llamadas y no
# contenga lógica de negocio ni bloques de debug.
#
# Si se necesita exponer información adicional para debug o análisis, se debe agregar un
# parámetro opcional (por ejemplo, debug=True) a la función de proceso, o retornar información
# adicional desde la función, pero nunca insertar prints, cálculos o lógica de análisis
# directamente en main.
#
# Cuando se solicite un cambio, asegúrate de:
# - No modificar main para lógica de análisis, debug o impresión de valores.
# - Implementar toda la lógica nueva o de debug en las funciones de proceso.
# - Si es necesario, crear nuevas funciones de proceso reutilizables para análisis o debug.
# - main debe limitarse a orquestar el flujo y llamar a las funciones de proceso.
# =============================================================================
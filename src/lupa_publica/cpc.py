"""Plain-language names for CPC divisions (first 2 digits of the CPC code).

SERCOP classifies items with Ecuador's CPC, built on the United Nations Central Product
Classification (CPC Ver. 2.1). Titles below are our own Spanish translation of the UN
division titles, shortened for readers who are not procurement experts.
"""

from __future__ import annotations

CPC_DIVISIONS: dict[str, str] = {
    "01": "Productos agrícolas",
    "02": "Animales vivos y productos animales",
    "03": "Productos forestales",
    "04": "Pescado y productos de la pesca",
    "11": "Carbón",
    "12": "Petróleo crudo y gas natural",
    "13": "Minerales de uranio y torio",
    "14": "Minerales metálicos",
    "15": "Piedra, arena y arcilla",
    "16": "Otros minerales",
    "17": "Electricidad, gas y agua caliente",
    "18": "Agua natural",
    "21": "Carne, pescado, frutas, verduras y aceites",
    "22": "Productos lácteos",
    "23": "Productos de molinería y otros alimentos",
    "24": "Bebidas",
    "25": "Productos de tabaco",
    "26": "Hilados y tejidos",
    "27": "Artículos textiles (excepto ropa)",
    "28": "Tejidos de punto y prendas de vestir",
    "29": "Cuero y calzado",
    "31": "Productos de madera",
    "32": "Papel e impresos",
    "33": "Combustibles y derivados del petróleo",
    "34": "Productos químicos básicos",
    "35": "Otros productos químicos y medicamentos",
    "36": "Productos de caucho y plástico",
    "37": "Vidrio, cemento y otros productos minerales",
    "38": "Muebles y otros bienes",
    "39": "Desechos y chatarra",
    "41": "Metales básicos",
    "42": "Productos metálicos",
    "43": "Maquinaria de uso general",
    "44": "Maquinaria de uso especial",
    "45": "Equipos de oficina y computación",
    "46": "Maquinaria y aparatos eléctricos",
    "47": "Equipos de radio, televisión y comunicaciones",
    "48": "Equipos médicos, de precisión y ópticos",
    "49": "Equipos de transporte",
    "53": "Obras de construcción",
    "54": "Servicios de construcción",
    "61": "Comercio al por mayor",
    "62": "Comercio al por menor",
    "63": "Alojamiento y alimentación",
    "64": "Transporte de pasajeros",
    "65": "Transporte de carga",
    "66": "Alquiler de vehículos con conductor",
    "67": "Servicios de apoyo al transporte",
    "68": "Correo y mensajería",
    "69": "Distribución de electricidad, gas y agua",
    "71": "Servicios financieros",
    "72": "Servicios inmobiliarios",
    "73": "Alquiler sin operario",
    "81": "Investigación y desarrollo",
    "82": "Servicios jurídicos y contables",
    "83": "Otros servicios profesionales y técnicos",
    "84": "Telecomunicaciones e información",
    "85": "Servicios de apoyo",
    "86": "Servicios de apoyo a agricultura, minería y servicios básicos",
    "87": "Mantenimiento, reparación e instalación",
    "88": "Fabricación por encargo",
    "89": "Otros servicios de fabricación e impresión",
    "91": "Administración pública",
    "92": "Educación",
    "93": "Salud y asistencia social",
    "94": "Alcantarillado y recolección de desechos",
    "95": "Servicios de organizaciones",
    "96": "Servicios recreativos, culturales y deportivos",
    "97": "Otros servicios",
    "98": "Servicio doméstico",
    "99": "Organismos internacionales",
}


def cpc_division_name(code: str | None) -> str:
    """Readable name for a 2-digit CPC division, or a neutral fallback."""
    if code and code in CPC_DIVISIONS:
        return CPC_DIVISIONS[code]
    return f"Categoría CPC {code}" if code and code != "unknown" else "Sin categoría"

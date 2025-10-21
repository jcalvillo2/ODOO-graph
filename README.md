# Odoo Dependency Tracker

Una herramienta para analizar y visualizar dependencias de módulos en Odoo usando grafos con Neo4j.

## Descripción

Odoo Dependency Tracker te ayuda a navegar y entender las dependencias entre módulos de Odoo. Cuando desarrollas un módulo nuevo y necesitas saber:
- En qué módulo está definido un modelo
- Qué campos tiene disponibles un modelo
- Qué dependencias necesita tu módulo
- Cómo están relacionados los módulos entre sí

Esta herramienta te proporciona respuestas rápidas mediante un grafo almacenado en Neo4j.

## Características

- Indexa módulos de Odoo desde directorios de addons
- Parsea archivos `__manifest__.py` para extraer dependencias
- Parsea modelos usando AST (Abstract Syntax Tree) sin ejecutar código
- Almacena relaciones en Neo4j para consultas rápidas
- CLI intuitivo con formato bonito usando Rich
- Búsqueda de modelos, campos y dependencias

## Requisitos

- Python 3.11+
- Docker (para Neo4j)
- Docker Compose

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/yourusername/odoo-dependency-tracker.git
cd odoo-dependency-tracker
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### 5. Levantar Neo4j con Docker

```bash
docker-compose up -d
```

Verifica que Neo4j esté corriendo:
```bash
curl http://localhost:7474
```

Accede a la interfaz web de Neo4j en: http://localhost:7474

## Uso

### Indexar módulos de Odoo

```bash
python main.py index /path/to/odoo/addons
```

Para limpiar la base de datos antes de indexar:
```bash
python main.py index /path/to/odoo/addons --clear
```

### Ver dependencias de un módulo

```bash
python main.py dependencies sale
```

Con dependencias recursivas:
```bash
python main.py dependencies sale --recursive
```

### Encontrar en qué módulo está definido un modelo

```bash
python main.py find-model sale.order
```

Salida:
```
Modelo: sale.order
Definido en: módulo 'sale'
Archivo: /opt/odoo/addons/sale/models/sale_order.py
Hereda de: mail.thread, mail.activity.mixin
```

### Ver campos de un modelo

```bash
python main.py show-fields sale.order
```

### Buscar un campo en todos los modelos

```bash
python main.py find-field partner_id
```

### Listar modelos de un módulo

```bash
python main.py list-models sale
```

## Estructura del Proyecto

```
odoo-dependency-tracker/
├── src/
│   ├── parser/
│   │   ├── manifest_parser.py    # Parser de __manifest__.py
│   │   └── model_parser.py       # Parser AST de modelos
│   ├── graph/
│   │   └── neo4j_client.py       # Cliente Neo4j
│   ├── cli/
│   │   └── commands.py           # Comandos Click
│   └── utils/
│       └── logger.py
├── tests/
│   ├── test_manifest_parser.py
│   └── test_model_parser.py
├── docker-compose.yml
├── requirements.txt
├── setup.py
├── main.py
├── CLAUDE.md
└── README.md
```

## Ejecutar Tests

```bash
pytest
```

Con cobertura:
```bash
pytest --cov=src --cov-report=html
```

## Modelo de Datos

### Nodos

**Module**: Representa un módulo de Odoo
- name: Nombre del módulo
- version: Versión
- category: Categoría
- installable: Si es instalable

**Model**: Representa un modelo/clase de Odoo
- name: Nombre del modelo (ej: `sale.order`)
- module: Módulo donde está definido
- file_path: Ruta al archivo .py
- fields: Diccionario de campos

### Relaciones

- `(Module)-[:DEPENDS_ON]->(Module)`: Dependencia entre módulos
- `(Model)-[:INHERITS_FROM]->(Model)`: Herencia entre modelos
- `(Model)-[:DELEGATES_TO]->(Model)`: Delegación (_inherits)
- `(Model)-[:DEFINED_IN]->(Module)`: Modelo definido en módulo

## Roadmap

- [ ] Parser de vistas XML
- [ ] Detección de dependencias circulares
- [ ] Exportar grafo a GraphML
- [ ] Visualización web del grafo
- [ ] Búsqueda de rutas entre módulos
- [ ] Análisis de impacto de cambios

## Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

MIT License - ver archivo LICENSE para detalles

## Soporte

Para preguntas o issues, por favor abre un issue en GitHub.

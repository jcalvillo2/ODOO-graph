# CLAUDE.md

Este archivo proporciona orientación a Claude Code (claude.ai/code) para el desarrollo desde cero de una herramienta de tracking de dependencias de módulos en Odoo.

## Instrucciones para Claude Code

### Metodología de Desarrollo

**IMPORTANTE**: Antes de proporcionar cualquier solución de código:

1. **PENSAR**: Analiza el panorama completo del problema
   - ¿Cómo encaja esta pieza en la arquitectura general?
   - ¿Qué otras partes del sistema se verán afectadas?
   - ¿Existen dependencias o prerequisitos?
   - ¿Hay edge cases o casos especiales a considerar?
   - **¿Es esta solución escalable y eficiente en memoria?**

2. **PLANIFICAR**: Diseña la solución antes de codificar
   - Describe el enfoque a alto nivel
   - Identifica los pasos necesarios
   - Considera alternativas si es relevante
   - Menciona posibles problemas o limitaciones
   - **Evalúa el impacto en performance y uso de memoria**

3. **IMPLEMENTAR**: Luego proporciona el código
   - Todo el código debe estar en **INGLÉS** (nombres de variables, funciones, clases, comentarios)
   - Los docstrings deben estar en inglés
   - Solo los mensajes de usuario (CLI, logs) pueden estar en español
   - **El código debe ser eficiente y escalable**

4. **VALIDAR**: Explica cómo probar la solución
   - ¿Qué tests se deberían escribir?
   - ¿Cómo se puede verificar que funciona correctamente?
   - **¿Cómo se puede medir el performance?**

### Estándares de Código

```python
# ✅ CORRECTO - Todo en inglés
class ManifestParser:
    """
    Parser for Odoo __manifest__.py files.
    
    This parser extracts metadata and dependencies from Odoo module manifests.
    """
    
    def parse_manifest(self, file_path: str) -> dict:
        """
        Parse a manifest file and extract relevant information.
        
        Args:
            file_path: Path to the __manifest__.py file
            
        Returns:
            Dictionary containing manifest data
        """
        module_name = self._extract_name(file_path)
        dependencies = self._extract_dependencies(file_path)
        
        return {
            "name": module_name,
            "dependencies": dependencies
        }

# ❌ INCORRECTO - Mezcla de idiomas
class AnalizadorManifest:
    """Parser para archivos __manifest__.py de Odoo"""
    
    def analizar_manifest(self, ruta_archivo: str) -> dict:
        nombre_modulo = self._extraer_nombre(ruta_archivo)
        return {"nombre": nombre_modulo}
```

### Mensajes de Usuario (Permitido en Español)

```python
# ✅ Mensajes CLI en español están bien
@click.command()
def index():
    """Indexa módulos de Odoo en Neo4j"""
    click.echo("Iniciando indexación...")
    click.echo(f"Módulos encontrados: {count}")
    
# ✅ Logs en español están bien
logger.info("Procesando módulo: sale")
logger.error("Error al conectar con Neo4j")
```

## Visión del Proyecto

Queremos construir una herramienta en Python que analice las dependencias de módulos en Odoo. El objetivo es ayudar a los desarrolladores de Odoo a acelerar su proceso de desarrollo, permitiéndoles encontrar rápidamente información sobre dependencias y relaciones entre módulos.

### Problema que Resuelve

Cuando un desarrollador de Odoo crea un módulo nuevo y agrega dependencias en su archivo `__manifest__.py`, a menudo no sabe exactamente dónde buscar lo que necesita. Esta herramienta le dirá:
- En qué módulos está definido un modelo
- Qué campos tiene disponibles un modelo
- Qué dependencias necesita su módulo
- Cómo están relacionados los módulos entre sí

### Ejemplo de Uso Esperado
```bash
# El desarrollador quiere extender sale.order
$ python main.py find-model sale.order
Modelo 'sale.order' definido en módulo: sale
Hereda de: mail.thread, mail.activity.mixin

# Ver qué campos tiene disponibles
$ python main.py show-fields sale.order
Campos en 'sale.order':
- partner_id: Many2one('res.partner')
- order_line: One2many('sale.order.line')
- amount_total: Monetary
...
```

## Requisitos de Escalabilidad y Performance

### Contexto del Problema

Un proyecto Odoo típico puede contener:
- **50-500+ módulos** (community + enterprise + custom)
- **1,000-5,000+ archivos Python**
- **2,000-10,000+ modelos y vistas**
- **Tamaño total: 500MB - 2GB+** de código

**DESAFÍO**: La herramienta debe ser capaz de escanear todo esto de manera eficiente, sin consumir memoria excesiva ni tomar demasiado tiempo.

### Objetivos de Performance

| Escenario | Objetivo | Métrica |
|-----------|----------|---------|
| Módulos pequeños (< 50) | < 30 segundos | Indexación completa |
| Módulos medianos (50-200) | < 2 minutos | Indexación completa |
| Módulos grandes (200-500) | < 10 minutos | Indexación completa |
| Enterprise completo (500+) | < 30 minutos | Indexación completa |
| Uso de memoria | < 500 MB | Pico de RAM |
| Re-indexación incremental | < 10% del tiempo total | Solo módulos modificados |

### Principios de Arquitectura Escalable

#### 1. **Procesamiento por Lotes (Batch Processing)**

```python
# ✅ CORRECTO - Procesar en lotes
def index_modules(module_paths: List[str], batch_size: int = 50):
    """
    Index modules in batches to avoid memory issues.
    
    Args:
        module_paths: List of paths to modules
        batch_size: Number of modules to process at once
    """
    for i in range(0, len(module_paths), batch_size):
        batch = module_paths[i:i + batch_size]
        process_batch(batch)
        # Memory is freed between batches

# ❌ INCORRECTO - Cargar todo en memoria
def index_modules(module_paths: List[str]):
    all_data = []
    for path in module_paths:
        all_data.append(parse_module(path))  # Acumula en memoria
    save_to_neo4j(all_data)  # Puede causar OutOfMemory
```

#### 2. **Streaming/Generadores en lugar de Listas**

```python
# ✅ CORRECTO - Usar generadores
def find_python_files(directory: str) -> Generator[str, None, None]:
    """
    Yield Python files one at a time instead of loading all in memory.
    """
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                yield os.path.join(root, file)

# Uso
for py_file in find_python_files('/opt/odoo/addons'):
    process_file(py_file)  # Procesa uno a la vez

# ❌ INCORRECTO - Cargar todas las rutas en memoria
def find_python_files(directory: str) -> List[str]:
    all_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                all_files.append(os.path.join(root, file))
    return all_files  # Puede ser miles de archivos en memoria
```

#### 3. **Procesamiento Lazy (Perezoso)**

```python
# ✅ CORRECTO - Parse solo cuando sea necesario
class ModuleParser:
    def __init__(self, module_path: str):
        self.module_path = module_path
        self._manifest = None
        self._models = None
    
    @property
    def manifest(self) -> dict:
        """Lazy load manifest only when accessed."""
        if self._manifest is None:
            self._manifest = self._parse_manifest()
        return self._manifest
    
    @property
    def models(self) -> List[dict]:
        """Lazy load models only when accessed."""
        if self._models is None:
            self._models = self._parse_models()
        return self._models

# ❌ INCORRECTO - Parse todo inmediatamente
class ModuleParser:
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.manifest = self._parse_manifest()  # Parse inmediato
        self.models = self._parse_models()      # Parse inmediato
        self.views = self._parse_views()        # Parse inmediato
        # Todo cargado aunque no se use
```

#### 4. **Transacciones en Lotes con Neo4j**

```python
# ✅ CORRECTO - Usar transacciones en lote
def save_models_batch(session, models: List[dict], batch_size: int = 100):
    """
    Save models to Neo4j in batches using transactions.
    """
    for i in range(0, len(models), batch_size):
        batch = models[i:i + batch_size]
        
        with session.begin_transaction() as tx:
            for model in batch:
                tx.run(
                    "CREATE (m:Model {name: $name, fields: $fields})",
                    name=model['name'],
                    fields=model['fields']
                )
            tx.commit()

# ❌ INCORRECTO - Una transacción por modelo
def save_models(session, models: List[dict]):
    for model in models:
        session.run(
            "CREATE (m:Model {name: $name, fields: $fields})",
            name=model['name'],
            fields=model['fields']
        )  # Miles de transacciones individuales = muy lento
```

#### 5. **Caché Inteligente**

```python
# ✅ CORRECTO - Cachear resultados de parsing AST
import hashlib
from functools import lru_cache

class CachedParser:
    def __init__(self, cache_dir: str = '.cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def parse_file(self, file_path: str) -> dict:
        """
        Parse file with caching based on file hash.
        Only re-parse if file has changed.
        """
        file_hash = self._get_file_hash(file_path)
        cache_path = self.cache_dir / f"{file_hash}.json"
        
        if cache_path.exists():
            # Return cached result
            with open(cache_path, 'r') as f:
                return json.load(f)
        
        # Parse and cache
        result = self._parse_ast(file_path)
        with open(cache_path, 'w') as f:
            json.dump(result, f)
        
        return result
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get hash of file content."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

# ❌ INCORRECTO - Re-parsear siempre
def parse_file(file_path: str) -> dict:
    return parse_ast(file_path)  # Siempre parsea desde cero
```

#### 6. **Procesamiento Paralelo (Opcional)**

```python
# ✅ CORRECTO - Usar multiprocessing para archivos grandes
from concurrent.futures import ProcessPoolExecutor
from typing import List

def parse_modules_parallel(module_paths: List[str], max_workers: int = 4):
    """
    Parse modules in parallel using multiple processes.
    
    Note: Only use for large datasets (200+ modules)
    """
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(parse_single_module, module_paths)
    
    return list(results)

def parse_single_module(module_path: str) -> dict:
    """Parse a single module - safe for multiprocessing."""
    parser = ModuleParser(module_path)
    return parser.extract_data()

# ⚠️ NOTA: Solo usar parallelización si hay > 200 módulos
# Para proyectos pequeños, el overhead no vale la pena
```

#### 7. **Índices de Neo4j**

```python
# ✅ CORRECTO - Crear índices antes de insertar datos
def setup_neo4j_indexes(session):
    """
    Create indexes on frequently queried fields.
    This dramatically speeds up queries.
    """
    indexes = [
        "CREATE INDEX module_name IF NOT EXISTS FOR (m:Module) ON (m.name)",
        "CREATE INDEX model_name IF NOT EXISTS FOR (m:Model) ON (m.name)",
        "CREATE INDEX model_module IF NOT EXISTS FOR (m:Model) ON (m.module)",
        "CREATE INDEX view_id IF NOT EXISTS FOR (v:View) ON (v.id)",
        "CREATE INDEX view_model IF NOT EXISTS FOR (v:View) ON (v.model)",
    ]
    
    for index_query in indexes:
        session.run(index_query)

# ❌ INCORRECTO - No crear índices
# Las queries serán muy lentas sin índices
```

### Estrategias de Optimización

#### Estrategia 1: Indexación Incremental

```python
class IncrementalIndexer:
    """
    Only re-index modules that have changed since last run.
    """
    
    def __init__(self, cache_file: str = '.last_index.json'):
        self.cache_file = cache_file
        self.last_index = self._load_last_index()
    
    def should_reindex(self, module_path: str) -> bool:
        """
        Check if module should be re-indexed based on modification time.
        """
        current_mtime = os.path.getmtime(module_path)
        last_mtime = self.last_index.get(module_path, 0)
        
        return current_mtime > last_mtime
    
    def index_modules(self, module_paths: List[str]):
        """Index only changed modules."""
        modules_to_index = [
            path for path in module_paths 
            if self.should_reindex(path)
        ]
        
        logger.info(f"Indexando {len(modules_to_index)} de {len(module_paths)} módulos")
        
        for module_path in modules_to_index:
            self.index_module(module_path)
            self.last_index[module_path] = os.path.getmtime(module_path)
        
        self._save_last_index()
```

#### Estrategia 2: Límites de Memoria

```python
import psutil

class MemoryAwareParser:
    """
    Monitor memory usage and adjust batch size dynamically.
    """
    
    def __init__(self, max_memory_percent: float = 70.0):
        self.max_memory_percent = max_memory_percent
    
    def get_safe_batch_size(self, default_size: int = 50) -> int:
        """
        Adjust batch size based on available memory.
        """
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        if memory_percent > self.max_memory_percent:
            # Reduce batch size if memory is high
            return max(10, default_size // 2)
        else:
            return default_size
    
    def process_with_memory_check(self, items: List[Any]):
        """Process items with memory monitoring."""
        batch_size = self.get_safe_batch_size()
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            self.process_batch(batch)
            
            # Check memory after each batch
            if psutil.virtual_memory().percent > self.max_memory_percent:
                logger.warning("Memoria alta, reduciendo tamaño de lote")
                batch_size = max(10, batch_size // 2)
```

#### Estrategia 3: Limpieza de Memoria

```python
import gc

def process_large_dataset(items: List[Any]):
    """
    Process large dataset with explicit memory cleanup.
    """
    for i, item in enumerate(items):
        process_item(item)
        
        # Force garbage collection every 100 items
        if i % 100 == 0:
            gc.collect()
            logger.debug(f"Processed {i}/{len(items)} items, memoria liberada")
```

### Métricas y Monitoreo

```python
import time
from contextlib import contextmanager

@contextmanager
def performance_monitor(operation_name: str):
    """
    Context manager to monitor performance of operations.
    """
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    
    yield
    
    end_time = time.time()
    end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    
    duration = end_time - start_time
    memory_delta = end_memory - start_memory
    
    logger.info(
        f"{operation_name}: {duration:.2f}s, "
        f"Memoria: {start_memory:.1f}MB -> {end_memory:.1f}MB "
        f"(Δ {memory_delta:+.1f}MB)"
    )

# Uso
with performance_monitor("Indexación de módulos"):
    index_all_modules(module_paths)
```

### Recomendaciones de Implementación

#### Para Proyectos Pequeños (< 50 módulos)
- Procesamiento simple secuencial
- Sin caché necesario
- Batch size: 50

#### Para Proyectos Medianos (50-200 módulos)
- Procesamiento en lotes (batch_size=50)
- Caché de archivos AST
- Índices de Neo4j
- Streaming con generadores

#### Para Proyectos Grandes (200-500 módulos)
- Todo lo anterior +
- Indexación incremental
- Monitoreo de memoria
- Batch size dinámico
- Considerar procesamiento paralelo

#### Para Enterprise Completo (500+ módulos)
- Todo lo anterior +
- Procesamiento paralelo (4-8 workers)
- Caché persistente en disco
- Limpieza de memoria explícita
- Progress bars detallados

### Banderas de Configuración

```python
# En .env o config
BATCH_SIZE=50                    # Número de módulos por lote
MAX_MEMORY_PERCENT=70.0         # % máximo de RAM a usar
ENABLE_CACHE=true               # Habilitar caché de AST
CACHE_DIR=.cache                # Directorio para caché
ENABLE_PARALLEL=false           # Procesamiento paralelo
MAX_WORKERS=4                   # Workers para parallel processing
ENABLE_INCREMENTAL=true         # Solo indexar cambios
```

## Conceptos Clave de Odoo

### Distinción Importante

- **Módulos**: Carpetas/paquetes de Odoo (ejemplos: `sale`, `base`, `stock`). No tienen puntos en el nombre.
- **Modelos**: Clases Python que representan tablas de BD (ejemplos: `sale.order`, `res.partner`). Tienen puntos en el nombre.

### Estructura de un Módulo Odoo
```
sale/
├── __manifest__.py          # Metadatos y dependencias
├── models/
│   ├── __init__.py
│   ├── sale_order.py        # Define sale.order
│   └── sale_order_line.py   # Define sale.order.line
├── views/
│   ├── sale_order_views.xml
│   └── sale_menus.xml
└── data/
```

### Ejemplo de `__manifest__.py`
```python
{
    'name': 'Sales Management',
    'version': '16.0.1.0',
    'depends': ['base', 'product', 'account'],
    'category': 'Sales',
    'installable': True,
}
```

### Ejemplo de Modelo en Odoo
```python
from odoo import models, fields

class SaleOrder(models.Model):
    _name = 'sale.order'           # Nombre del modelo
    _inherit = ['mail.thread']      # Herencia (añade funcionalidad)
    
    partner_id = fields.Many2one('res.partner', string='Customer')
    order_line = fields.One2many('sale.order.line', 'order_id')
    amount_total = fields.Monetary(string='Total')
```

### Tipos de Herencia en Odoo

1. **`_inherit`**: Herencia clásica - extiende un modelo existente
2. **`_inherits`**: Herencia por delegación - delega campos a otro modelo

## Arquitectura Propuesta

### Stack Tecnológico

- **Python 3.11+**: Lenguaje principal
- **Neo4j**: Base de datos de grafos para almacenar relaciones
- **AST (Abstract Syntax Tree)**: Para parsear archivos Python sin ejecutarlos
- **XML Parser (lxml/ElementTree)**: Para parsear vistas XML de Odoo
- **Click**: Framework para CLI
- **Rich**: Para formateo bonito en terminal
- **psutil**: Para monitoreo de memoria

### ¿Por qué Neo4j?

Neo4j es perfecto para este caso de uso porque:
- Las dependencias forman un grafo (módulos dependen de otros módulos)
- La herencia forma árboles (modelos heredan de otros modelos)
- Las vistas referencian modelos y otras vistas
- Cypher (lenguaje de queries) permite encontrar cadenas de dependencias fácilmente
- Visualización natural de relaciones
- Maneja grandes volúmenes de datos eficientemente

### Flujo de la Aplicación
```
1. INDEXACIÓN (Con optimizaciones)
   Directorios Odoo → Stream/Generator → 
   Parser AST (con caché) → 
   Batch Processing → 
   Neo4j (transacciones en lote) →
   Cache resultados
   
2. CONSULTA
   Usuario → CLI → Query a Neo4j (con índices) → 
   Formato con Rich → Terminal
```

## Modelo de Datos en Neo4j

### Nodos

**Module** (Módulo de Odoo)
```
Propiedades:
- name: string (ej: "sale")
- version: string (ej: "16.0.1.0")
- category: string (ej: "Sales")
- summary: string
- author: string
- installable: boolean
- file_hash: string (para detección de cambios)
- last_indexed: timestamp
```

**Model** (Modelo/Clase de Odoo)
```
Propiedades:
- name: string (ej: "sale.order")
- module: string (ej: "sale")
- file_path: string (ruta al archivo .py)
- fields: json (diccionario de campos)
- file_hash: string
- last_indexed: timestamp
```

**View** (Vista XML de Odoo)
```
Propiedades:
- id: string (ej: "view_order_form")
- model: string (modelo al que pertenece)
- type: string (form, tree, kanban, etc.)
- module: string (módulo que la define)
- file_path: string (ruta al archivo .xml)
- file_hash: string
- last_indexed: timestamp
```

### Relaciones
```
(Module)-[:DEPENDS_ON]->(Module)
// sale depende de product

(Model)-[:INHERITS_FROM]->(Model)
// sale.order hereda de mail.thread

(Model)-[:DELEGATES_TO]->(Model)
// Herencia por delegación (_inherits)

(Model)-[:DEFINED_IN]->(Module)
// sale.order está definido en el módulo sale

(View)-[:BELONGS_TO]->(Model)
// view_order_form pertenece a sale.order

(View)-[:INHERITS_VIEW]->(View)
// Una vista hereda/extiende otra vista

(View)-[:DEFINED_IN]->(Module)
// La vista está definida en un módulo
```

### Ejemplo de Grafo
```
(sale:Module)-[:DEPENDS_ON]->(product:Module)
(sale:Module)-[:DEPENDS_ON]->(account:Module)
(account:Module)-[:DEPENDS_ON]->(base:Module)

(sale.order:Model)-[:DEFINED_IN]->(sale:Module)
(sale.order:Model)-[:INHERITS_FROM]->(mail.thread:Model)
(mail.thread:Model)-[:DEFINED_IN]->(mail:Module)

(view_order_form:View)-[:BELONGS_TO]->(sale.order:Model)
(view_order_form:View)-[:DEFINED_IN]->(sale:Module)
```

## Plan de Desarrollo

### Fase 1: Setup Inicial
- [ ] Crear estructura de proyecto
- [ ] Configurar entorno virtual Python
- [ ] Setup de Neo4j con Docker
- [ ] Configurar variables de entorno
- [ ] **Implementar sistema de configuración con límites de memoria y batch size**

### Fase 2: Parser Básico
- [ ] Crear parser que lea `__manifest__.py`
- [ ] Extraer nombre, versión, dependencias del módulo
- [ ] **Implementar usando generadores (no listas)**
- [ ] Crear tests para el parser

### Fase 3: Parser AST para Modelos
- [ ] Implementar parser AST para archivos Python
- [ ] Detectar clases que son modelos Odoo (buscar `_name`, `_inherit`)
- [ ] Extraer campos del modelo (fields.Char, fields.Many2one, etc.)
- [ ] Manejar casos especiales (modelos sin `_name` explícito)
- [ ] **Implementar caché de resultados AST basado en hash de archivo**

### Fase 4: Integración con Neo4j
- [ ] Conexión a Neo4j
- [ ] **Crear índices ANTES de insertar datos**
- [ ] Crear nodos Module **en lotes (batch processing)**
- [ ] Crear nodos Model **en lotes**
- [ ] Crear relaciones DEPENDS_ON **en lotes**
- [ ] Crear relaciones INHERITS_FROM, DELEGATES_TO, DEFINED_IN **en lotes**
- [ ] **Implementar transacciones eficientes**

### Fase 5: CLI Básico
- [ ] Comando `index` - indexar módulos en un directorio
- [ ] **Agregar flag `--batch-size` para controlar tamaño de lote**
- [ ] **Agregar flag `--incremental` para indexación incremental**
- [ ] **Agregar progress bar con Rich**
- [ ] Comando `dependencies` - mostrar dependencias de un módulo
- [ ] Comando `find-model` - buscar dónde está definido un modelo
- [ ] Formateo con Rich

### Fase 6: Queries Avanzadas
- [ ] Comando `inheritance` - árbol de herencia de un modelo
- [ ] Comando `find-field` - buscar campo en todos los modelos
- [ ] Comando `list-models` - listar modelos de un módulo
- [ ] Detección de dependencias circulares
- [ ] **Todas las queries deben aprovechar índices de Neo4j**

### Fase 7: Parser de Vistas XML
- [ ] Implementar parser XML para archivos de vistas
- [ ] **Usar streaming XML parser para archivos grandes**
- [ ] Extraer información de vistas (id, modelo, tipo)
- [ ] Detectar herencia de vistas (inherit_id)
- [ ] Crear nodos View en Neo4j **en lotes**
- [ ] Crear relaciones BELONGS_TO, INHERITS_VIEW, DEFINED_IN **en lotes**

### Fase 8: Queries de Vistas
- [ ] Comando `find-view` - buscar vistas de un modelo
- [ ] Comando `view-inheritance` - árbol de herencia de vistas
- [ ] Comando `list-views` - listar vistas de un módulo

### Fase 9: Optimizaciones
- [ ] **Implementar indexación incremental completa**
- [ ] **Sistema de caché persistente**
- [ ] **Monitoreo de memoria con psutil**
- [ ] **Procesamiento paralelo opcional (para > 200 módulos)**
- [ ] **Métricas de performance detalladas**
- [ ] Manejo de errores robusto
- [ ] Logging
- [ ] Documentación completa

## Estructura de Directorios Objetivo
```
odoo-dependency-tracker/
├── src/
│   ├── __init__.py
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── manifest_parser.py    # Parser de __manifest__.py
│   │   ├── model_parser.py       # Parser AST de modelos
│   │   ├── view_parser.py        # Parser XML de vistas
│   │   └── cache.py              # Sistema de caché
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── neo4j_client.py       # Cliente Neo4j
│   │   └── batch_writer.py       # Escritura en lotes
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py           # Comandos Click
│   ├── indexer/
│   │   ├── __init__.py
│   │   ├── incremental.py        # Indexación incremental
│   │   └── parallel.py           # Procesamiento paralelo
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── memory_monitor.py     # Monitor de memoria
│       └── performance.py        # Métricas de performance
├── tests/
│   ├── __init__.py
│   ├── fixtures/                 # Módulos Odoo de prueba
│   ├── test_manifest_parser.py
│   ├── test_model_parser.py
│   ├── test_view_parser.py
│   ├── test_neo4j_client.py
│   ├── test_cache.py
│   └── test_performance.py       # Tests de performance
├── .cache/                        # Caché de AST (git ignore)
├── .env.example
├── .gitignore
├── docker-compose.yml            # Para Neo4j
├── requirements.txt
├── setup.py
├── README.md
├── CLAUDE.md
└── main.py                       # Entry point
```

## Setup Inicial

### 1. requirements.txt
```
neo4j>=5.14.0
click>=8.1.0
rich>=13.0.0
python-dotenv>=1.0.0
lxml>=4.9.0
pytest>=7.4.0
pytest-cov>=4.1.0
psutil>=5.9.0
```

### 2. .env.example
```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here

# Odoo Addons Paths (comma separated)
ADDONS_PATHS=/opt/odoo/addons,/opt/odoo/custom

# Performance Settings
BATCH_SIZE=50
MAX_MEMORY_PERCENT=70.0
ENABLE_CACHE=true
CACHE_DIR=.cache
ENABLE_PARALLEL=false
MAX_WORKERS=4
ENABLE_INCREMENTAL=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=odoo_tracker.log
```

### 3. docker-compose.yml
```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.13
    container_name: odoo-tracker-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/your-password-here
      - NEO4J_PLUGINS=["apoc"]
      # Optimizaciones de memoria para Neo4j
      - NEO4J_server_memory_heap_initial__size=512M
      - NEO4J_server_memory_heap_max__size=2G
      - NEO4J_server_memory_pagecache_size=1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs

volumes:
  neo4j_data:
  neo4j_logs:
```

### 4. Comandos de inicio
```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Levantar Neo4j
docker-compose up -d

# Verificar que Neo4j está corriendo
curl http://localhost:7474

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus valores

# Crear directorio de caché
mkdir -p .cache
```

## Conceptos Técnicos Importantes

### Parsing con AST

AST (Abstract Syntax Tree) permite analizar código Python sin ejecutarlo:
```python
import ast

# Read Python file
with open('sale_order.py', 'r') as f:
    tree = ast.parse(f.read())

# Find classes
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        print(f"Class found: {node.name}")
        
        # Find class attributes
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        print(f"  Attribute: {target.id}")
```

### Parsing de Vistas XML

```python
from lxml import etree

# Parse XML file efficiently
tree = etree.parse('sale_order_views.xml')
root = tree.getroot()

# Find all view records
for record in root.xpath("//record[@model='ir.ui.view']"):
    view_id = record.get('id')
    
    # Extract view information
    for field in record.findall('field'):
        field_name = field.get('name')
        field_value = field.text
        
        if field_name == 'model':
            print(f"View {view_id} belongs to model: {field_value}")
        elif field_name == 'inherit_id':
            inherit_ref = field.get('ref')
            print(f"View {view_id} inherits from: {inherit_ref}")
```

### Queries Cypher Básicos
```cypher
// Crear nodo Module
CREATE (m:Module {name: 'sale', version: '16.0.1.0'})

// Crear relación DEPENDS_ON
MATCH (a:Module {name: 'sale'})
MATCH (b:Module {name: 'product'})
CREATE (a)-[:DEPENDS_ON]->(b)

// Buscar dependencias (usa índice en Module.name)
MATCH (m:Module {name: 'sale'})-[:DEPENDS_ON]->(dep)
RETURN dep.name

// Buscar dependencias recursivas
MATCH path = (m:Module {name: 'sale'})-[:DEPENDS_ON*]->(dep)
RETURN path

// Buscar vistas de un modelo (usa índice en View.model)
MATCH (v:View)-[:BELONGS_TO]->(m:Model {name: 'sale.order'})
RETURN v.id, v.type

// Árbol de herencia de vistas
MATCH path = (v:View {id: 'view_order_form'})-[:INHERITS_VIEW*]->(parent:View)
RETURN path

// Batch insert con UNWIND (mucho más rápido)
UNWIND $batch as item
CREATE (m:Module {
  name: item.name,
  version: item.version,
  category: item.category
})
```

## Casos de Uso a Implementar

### Modelos

#### Caso 1: Encontrar definición de modelo
```bash
$ python main.py find-model sale.order
Modelo: sale.order
Definido en: módulo 'sale'
Archivo: /opt/odoo/addons/sale/models/sale_order.py
```

#### Caso 2: Ver dependencias de módulo
```bash
$ python main.py dependencies sale --recursive
sale
├── product
├── account
│   └── base
└── stock
    └── product
```

#### Caso 3: Ver herencia de modelo
```bash
$ python main.py inheritance sale.order
sale.order (definido en: sale)
└── hereda de: mail.thread (definido en: mail)
    └── hereda de: mail.activity.mixin (definido en: mail)
```

#### Caso 4: Buscar campo en todos los modelos
```bash
$ python main.py find-field partner_id
Campo 'partner_id' encontrado en:
- sale.order (sale): Many2one('res.partner')
- account.move (account): Many2one('res.partner')
- stock.picking (stock): Many2one('res.partner')
```

### Vistas

#### Caso 5: Listar vistas de un modelo
```bash
$ python main.py find-view sale.order
Vistas para 'sale.order':
- view_order_form (form) - definida en: sale
- view_quotation_tree (tree) - definida en: sale
- view_order_kanban (kanban) - definida en: sale
- view_order_calendar (calendar) - definida en: sale
```

#### Caso 6: Ver herencia de una vista
```bash
$ python main.py view-inheritance sale.view_order_form
view_order_form (sale)
├── extendida por: sale_stock.view_order_form_inherit (sale_stock)
├── extendida por: sale_crm.view_order_form_crm (sale_crm)
└── extendida por: custom_sale.view_order_form_custom (custom_sale)
```

#### Caso 7: Buscar todas las vistas de un módulo
```bash
$ python main.py list-views sale
Vistas en módulo 'sale':
Models:
  sale.order:
    - view_order_form (form)
    - view_quotation_tree (tree)
  sale.order.line:
    - view_order_line_form (form)
    - view_order_line_tree (tree)
```

### Performance y Optimización

#### Caso 8: Indexación con progress y stats
```bash
$ python main.py index /opt/odoo/addons --stats
Escaneando directorios...
Módulos encontrados: 347

[████████████████████████████████████████] 100% 347/347

Resultados:
  Tiempo total: 4m 32s
  Módulos indexados: 347
  Modelos extraídos: 2,451
  Vistas extraídas: 3,789
  Memoria pico: 342 MB
  Promedio: 0.78s por módulo
  
  Detalles:
    - Módulos nuevos: 23
    - Módulos actualizados: 18
    - Módulos sin cambios: 306 (omitidos)
```

#### Caso 9: Indexación incremental
```bash
$ python main.py index /opt/odoo/addons --incremental
Modo incremental activado
Analizando cambios desde última indexación...

Cambios detectados:
  - Módulos modificados: 5
  - Módulos nuevos: 2
  - Total a indexar: 7 de 347

[████████████████████████████████████████] 100% 7/7

Indexación completada en 18s
Memoria usada: 89 MB
```

#### Caso 10: Benchmark y optimización
```bash
$ python main.py benchmark /opt/odoo/addons

=== BENCHMARK DE PERFORMANCE ===

Configuración actual:
  Batch size: 50
  Caché: Habilitado
  Procesamiento paralelo: Deshabilitado
  Indexación incremental: Habilitado

Resultados:
  Test 1: Parse de manifest
    Promedio: 0.003s por archivo
    Total: 1.04s para 347 archivos
  
  Test 2: Parse AST de modelos
    Promedio: 0.041s por archivo
    Total: 42.3s para 1,032 archivos
    Caché hit rate: 87%
  
  Test 3: Parse XML de vistas
    Promedio: 0.019s por archivo
    Total: 23.1s para 1,215 archivos
  
  Test 4: Escritura a Neo4j
    Batch insert: 0.234s para 50 items
    Individual insert: 4.823s para 50 items
    Mejora: 20.6x más rápido con batch
  
Recomendaciones:
  ✓ Batch size de 50 es óptimo para tu dataset
  ✓ Caché funcionando correctamente
  ⚠ Considera habilitar procesamiento paralelo (>200 módulos detectados)
```

## Desafíos Técnicos Esperados

### Modelos

#### 1. Modelos sin `_name` explícito

Algunos modelos solo tienen `_inherit`:
```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'  # Extiende, no define
    
    new_field = fields.Char()
```

**Solución**: Si no hay `_name`, usar el primer valor de `_inherit` como nombre del modelo.

#### 2. Herencia múltiple
```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

**Solución**: Crear múltiples relaciones INHERITS_FROM.

#### 3. Campos computados
```python
amount_total = fields.Monetary(compute='_compute_amount')
```

**Solución**: Capturar todos los campos, incluso sin tipo explícito.

#### 4. Módulos con errores de sintaxis

**Solución**: Try/catch en el parser, log el error, continuar con otros módulos. No debe detener toda la indexación.

### Vistas

#### 5. Referencias a vistas externas

```xml
<field name="inherit_id" ref="sale.view_order_form"/>
```

**Solución**: Parsear el atributo `ref` y crear relación con la vista padre. El formato es `module.view_id`.

#### 6. Vistas sin ID explícito

Algunas vistas usan IDs generados automáticamente.

**Solución**: Si no hay ID, generar uno basado en el nombre del archivo y posición (ej: `file_name_view_1`).

#### 7. XPath en herencia de vistas

```xml
<xpath expr="//field[@name='partner_id']" position="after">
    <field name="custom_field"/>
</xpath>
```

**Solución**: No necesitamos parsear el XPath completamente, solo identificar que hay herencia.

### Performance

#### 8. Archivos Python muy grandes (> 5000 líneas)

**Solución**: 
- Implementar timeout en el parser AST (max 10s por archivo)
- Log warning si un archivo es muy grande
- Considerar parsear solo las clases, no el archivo completo

```python
import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()

def parse_with_timeout(file_path: str, timeout: int = 10):
    """Parse file with timeout to avoid hanging."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        result = parse_ast(file_path)
        signal.alarm(0)  # Cancel alarm
        return result
    except TimeoutException:
        logger.warning(f"Timeout parsing {file_path}, skipping")
        return None
```

#### 9. Muchos archivos pequeños (overhead de I/O)

**Solución**: Agrupar lectura de archivos y procesarlos en memoria.

```python
def batch_read_files(file_paths: List[str], batch_size: int = 100):
    """Read multiple files at once to reduce I/O overhead."""
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        
        # Read all files in batch
        file_contents = {}
        for path in batch:
            with open(path, 'r') as f:
                file_contents[path] = f.read()
        
        # Process in memory
        for path, content in file_contents.items():
            yield path, content
```

#### 10. Neo4j connection pool exhaustion

**Solución**: Usar connection pooling correctamente.

```python
from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        # Connection pool se maneja automáticamente
        self.driver = GraphDatabase.driver(
            uri, 
            auth=(user, password),
            max_connection_pool_size=50,  # Ajustar según necesidad
            connection_acquisition_timeout=60.0
        )
    
    def close(self):
        self.driver.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Uso con context manager
with Neo4jClient(uri, user, password) as client:
    client.index_modules(modules)
```

## Métricas de Éxito

El proyecto será exitoso si:
- ✅ Puede indexar módulos estándar de Odoo (base, sale, stock, etc.)
- ✅ **Indexa 500+ módulos en menos de 30 minutos**
- ✅ **Usa menos de 500MB de memoria en pico**
- ✅ Detecta correctamente dependencias de módulos
- ✅ Extrae modelos y sus campos
- ✅ Extrae vistas y sus relaciones
- ✅ Muestra árboles de herencia correctamente (modelos y vistas)
- ✅ **La indexación incremental es al menos 10x más rápida que indexación completa**
- ✅ CLI es intuitivo y rápido
- ✅ Maneja errores gracefully
- ✅ El código es mantenible y está bien documentado (en inglés)
- ✅ **Incluye métricas de performance visibles para el usuario**

## Ejemplos de Comandos CLI

### Comandos Básicos
```bash
# Indexar con configuración por defecto
python main.py index /opt/odoo/addons

# Indexar con opciones personalizadas
python main.py index /opt/odoo/addons \
  --batch-size 100 \
  --incremental \
  --verbose \
  --stats

# Indexar sin caché (forzar re-parse)
python main.py index /opt/odoo/addons --no-cache

# Indexar con procesamiento paralelo
python main.py index /opt/odoo/addons --parallel --workers 8

# Limpiar base de datos y re-indexar
python main.py index /opt/odoo/addons --clean
```

### Comandos de Consulta
```bash
# Buscar modelo
python main.py find-model sale.order

# Ver dependencias
python main.py dependencies sale --recursive

# Ver herencia de modelo
python main.py inheritance sale.order --full-tree

# Buscar campo
python main.py find-field partner_id --module sale

# Listar modelos de un módulo
python main.py list-models sale

# Buscar vistas
python main.py find-view sale.order

# Ver herencia de vistas
python main.py view-inheritance sale.view_order_form
```

### Comandos de Análisis
```bash
# Detectar dependencias circulares
python main.py check-circular

# Encontrar módulos no usados
python main.py find-unused

# Análisis de impacto
python main.py impact res.partner

# Estadísticas del proyecto
python main.py stats
# Output:
# === ESTADÍSTICAS DEL PROYECTO ===
# Módulos: 347
# Modelos: 2,451
# Vistas: 3,789
# Dependencias: 1,234
# 
# Top 5 módulos más dependidos:
# 1. base (234 dependencias)
# 2. mail (156 dependencias)
# 3. web (89 dependencias)
# ...
```

### Comandos de Mantenimiento
```bash
# Verificar integridad de datos
python main.py verify

# Limpiar caché
python main.py clear-cache

# Exportar datos
python main.py export --format json --output data.json

# Benchmark de performance
python main.py benchmark /opt/odoo/addons
```

## Próximos Pasos

1. **Fase 1-6**: Implementar funcionalidad base (modelos y dependencias) con optimizaciones
2. **Fase 7-8**: Agregar soporte para vistas XML con streaming
3. **Fase 9**: Optimizaciones finales y métricas

## Recursos de Referencia

### Documentación Odoo
- [Odoo Development Documentation](https://www.odoo.com/documentation/16.0/developer.html)
- [ORM API Reference](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)
- [Views Documentation](https://www.odoo.com/documentation/16.0/developer/reference/backend/views.html)

### Neo4j
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
- [Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Performance Tuning](https://neo4j.com/docs/operations-manual/current/performance/)

### Python AST
- [AST Module](https://docs.python.org/3/library/ast.html)
- [Green Tree Snakes Tutorial](https://greentreesnakes.readthedocs.io/)

### XML Parsing
- [lxml Documentation](https://lxml.de/tutorial.html)
- [ElementTree Documentation](https://docs.python.org/3/library/xml.etree.elementtree.html)

### Performance y Optimización
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [Memory Profiling in Python](https://docs.python.org/3/library/tracemalloc.html)
- [psutil Documentation](https://psutil.readthedocs.io/)

### Click (CLI)
- [Click Documentation](https://click.palletsprojects.com/)

### Rich (Terminal Formatting)
- [Rich Documentation](https://rich.readthedocs.io/)

## Glosario de Términos

### Performance
- **Batch Processing**: Procesar items en grupos en lugar de uno por uno
- **Streaming**: Procesar datos a medida que se leen, sin cargar todo en memoria
- **Lazy Loading**: Cargar datos solo cuando se necesitan
- **Caching**: Almacenar resultados para reutilizarlos
- **Indexing**: Crear índices en la base de datos para búsquedas rápidas
- **Connection Pooling**: Reutilizar conexiones de base de datos

### Odoo
- **Module**: Un addon/paquete de Odoo
- **Model**: Una clase Python que representa una tabla de base de datos
- **View**: Definición XML de interfaz de usuario
- **Inheritance**: Mecanismo para extender modelos o vistas existentes
- **Manifest**: Archivo `__manifest__.py` con metadatos del módulo

### Neo4j
- **Node**: Un registro en la base de datos de grafos
- **Relationship**: Una conexión entre dos nodos
- **Cypher**: Lenguaje de queries de Neo4j
- **Transaction**: Grupo de operaciones que se ejecutan como una unidad
- **Index**: Estructura para búsquedas rápidas en nodos

---

**Nota**: Este proyecto se construirá desde cero. Claude Code debe:

1. **PENSAR** en el panorama completo antes de codificar
   - Considerar escalabilidad y uso de memoria en cada decisión
   - Evaluar el impacto de cada feature en el performance global
   
2. **PLANIFICAR** la solución explicando el enfoque
   - Describir estrategias de optimización que se aplicarán
   - Mencionar trade-offs entre velocidad, memoria y complejidad
   
3. **IMPLEMENTAR** código en **INGLÉS** (variables, funciones, comentarios, docstrings)
   - Usar generadores en lugar de listas cuando sea posible
   - Implementar batch processing para operaciones masivas
   - Agregar métricas de performance donde sea relevante
   
4. **VALIDAR** sugiriendo tests apropiados
   - Incluir tests de performance para operaciones críticas
   - Sugerir benchmarks para medir mejoras

**PRINCIPIO FUNDAMENTAL**: Cada feature debe ser escalable desde el diseño inicial. No optimizar prematuramente, pero tampoco diseñar de forma que haga la optimización difícil después.

Los mensajes de usuario (CLI, logs) pueden estar en español, pero todo el código debe ser en inglés para mantener estándares profesionales.
```

¡Listo! Ahora tienes el archivo `CLAUDE.md` completo con todas las secciones de escalabilidad y performance integradas. El archivo está diseñado para guiar a Claude Code en la construcción de un proyecto eficiente desde el inicio. 🚀
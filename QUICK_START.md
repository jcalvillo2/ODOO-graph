# Quick Start Guide

Esta guía te ayudará a comenzar a usar Odoo Dependency Tracker en minutos.

## 1. Instalación Rápida

```bash
# Clonar repositorio
git clone <tu-repo>
cd odoo-dependency-tracker

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
```

## 2. Levantar Neo4j

```bash
# Iniciar Neo4j con Docker
docker-compose up -d

# Verificar que esté corriendo
curl http://localhost:7474
```

Accede a Neo4j Browser en: http://localhost:7474
- Usuario: `neo4j`
- Password: `your-password-here` (o el que configuraste en `.env`)

## 3. Indexar Módulos de Prueba

El proyecto incluye un módulo de prueba en `tests/fixtures/test_module/`:

```bash
# Indexar el módulo de prueba
python main.py index tests/fixtures/ --clear
```

Salida esperada:
```
Indexando módulos desde: tests/fixtures/
Limpiando base de datos...
Encontrados 1 módulos
Indexación completada!
  Módulos indexados: 1
  Modelos indexados: 3
```

## 4. Probar Comandos

### Ver dependencias del módulo
```bash
python main.py dependencies test_module
```

### Buscar un modelo
```bash
python main.py find-model test.order
```

Salida esperada:
```
Modelo: test.order
Definido en: módulo 'test_module'
Archivo: /path/to/tests/fixtures/test_module/models/order_model.py
Hereda de: mail.thread, mail.activity.mixin
```

### Ver campos del modelo
```bash
python main.py show-fields test.order
```

### Buscar campo en todos los modelos
```bash
python main.py find-field partner_id
```

### Listar modelos del módulo
```bash
python main.py list-models test_module
```

Salida esperada:
```
Modelos en 'test_module':
  res.partner
  test.order
  test.order.line
```

## 5. Indexar Módulos Reales de Odoo

Si tienes Odoo instalado localmente:

```bash
# Indexar addons de Odoo
python main.py index /path/to/odoo/addons --clear

# Indexar addons custom
python main.py index /path/to/custom_addons
```

Ejemplos con módulos reales:

```bash
# Buscar modelo sale.order
python main.py find-model sale.order

# Ver dependencias de sale
python main.py dependencies sale --recursive

# Ver campos de res.partner
python main.py show-fields res.partner

# Buscar campo partner_id en todos los modelos
python main.py find-field partner_id
```

## 6. Explorar en Neo4j Browser

Abre http://localhost:7474 y ejecuta estas queries:

```cypher
// Ver todos los módulos
MATCH (m:Module)
RETURN m.name, m.version, m.category
LIMIT 25

// Ver todos los modelos
MATCH (model:Model)
RETURN model.name, model.module
LIMIT 25

// Ver dependencias de un módulo
MATCH (m:Module {name: 'test_module'})-[:DEPENDS_ON]->(dep)
RETURN m.name, dep.name

// Ver árbol de herencia de un modelo
MATCH path = (m:Model {name: 'test.order'})-[:INHERITS_FROM*]->(parent)
RETURN path

// Ver todos los modelos de un módulo
MATCH (model:Model)-[:DEFINED_IN]->(m:Module {name: 'test_module'})
RETURN model.name, model.fields
```

## 7. Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=src --cov-report=html

# Ver reporte de cobertura
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
```

## 8. Detener Neo4j

```bash
# Detener contenedor
docker-compose down

# Detener y eliminar volúmenes (borra datos)
docker-compose down -v
```

## Troubleshooting

### Error: "No module named 'neo4j'"
```bash
pip install -r requirements.txt
```

### Error: "Connection refused to Neo4j"
```bash
# Verificar que Neo4j esté corriendo
docker-compose ps

# Ver logs
docker-compose logs neo4j

# Reiniciar
docker-compose restart
```

### Error: "Authentication failed"
Verifica las credenciales en `.env`:
```
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
```

## Próximos Pasos

1. Indexa tus propios módulos de Odoo
2. Explora las relaciones en Neo4j Browser
3. Usa los comandos CLI en tu flujo de desarrollo
4. Contribuye con nuevas features

Para más información, consulta [README.md](README.md) y [CLAUDE.md](CLAUDE.md).

# 🚀 Comandos para Probar el ETL Pipeline

## ✅ Lo que acabas de construir

Has generado un **sistema completo de ETL** para analizar código fuente de Odoo con:
- 6 módulos Python de producción
- 6 documentos de diseño técnico
- Scripts de prueba completos
- 606 módulos de Odoo descubiertos
- Miles de líneas de código funcionando

---

## 🎯 Prueba Rápida (30 segundos)

**Comando más simple - Solo extracción:**

```bash
python quick_test.py
```

**Resultado esperado:**
```
✅ Found 606 modules
✅ Found 12 models
✅ Found 15 views
✅ QUICK TEST COMPLETED!
```

---

## 📊 Prueba Completa con Guardado de Resultados

**Extrae TODO y guarda en JSON:**

```bash
python test_pipeline.py \
  --odoo-path ./odoo18/addons \
  --test-extract-only \
  --save-output
```

**Esto crea en `./output/`:**
- `modules.json` - Todos los módulos encontrados
- `models.json` - Todos los modelos extraídos
- `views.json` - Todas las vistas extraídas

**Ver estadísticas:**
```bash
# Ver cantidad de líneas en cada archivo
wc -l output/*.json

# Ver los primeros módulos extraídos
head -n 50 output/modules.json | jq '.'

# Contar modelos por tipo
jq '[.[] | .model_type] | group_by(.) | map({type: .[0], count: length})' output/models.json
```

---

## 🔍 Explorar los Datos Extraídos

### Ver módulos descubiertos:
```bash
jq '.[] | {name: .name, version: .version, depends: .depends[0:3]}' output/modules.json | head -n 50
```

### Ver modelos extraídos:
```bash
jq '.[] | {name: .name, type: .model_type, module: .module, fields: (.fields | length)}' output/models.json | head -n 20
```

### Ver vistas extraídas:
```bash
jq '.[] | {id: .xml_id, type: .view_type, model: .model}' output/views.json | head -n 20
```

### Buscar un modelo específico:
```bash
jq '.[] | select(.name == "sale.order")' output/models.json
```

### Buscar modelos de un módulo específico:
```bash
jq '.[] | select(.module == "sale")' output/models.json
```

---

## 🧪 Probar Componentes Individualmente

### 1. Probar el parser de módulos:
```bash
python src/extractor/parse_modules.py ./odoo18/addons | jq '.[0:3]'
```

### 2. Probar el indexador de modelos:
```bash
python src/extractor/index_models.py sale ./odoo18/addons/sale | jq '.'
```

### 3. Probar el indexador de vistas:
```bash
python src/extractor/index_views.py sale ./odoo18/addons/sale | jq '.'
```

---

## 🗄️ Prueba con Neo4j (Opcional - Requiere Docker)

Si quieres probar la carga en Neo4j:

### 1. Iniciar Neo4j con Docker:
```bash
docker run -d \
  --name neo4j-odoo \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/testpassword \
  neo4j:latest
```

### 2. Esperar que Neo4j arranque:
```bash
# Espera unos 30 segundos, luego verifica:
docker logs neo4j-odoo | grep "Started"
```

### 3. Instalar driver de Neo4j:
```bash
pip install neo4j
```

### 4. Ejecutar ETL completo con Neo4j:
```bash
python test_pipeline.py \
  --odoo-path ./odoo18/addons \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-password testpassword
```

### 5. Abrir Neo4j Browser:
```bash
# Abre en tu navegador:
http://localhost:7474

# Credenciales:
# Usuario: neo4j
# Password: testpassword
```

### 6. Ejecutar queries en Neo4j Browser:

**Contar todos los nodos:**
```cypher
MATCH (n) RETURN labels(n), count(n)
```

**Ver modelos:**
```cypher
MATCH (m:Model)
RETURN m.name, m.module, m.model_type
LIMIT 25
```

**Ver herencias de modelos:**
```cypher
MATCH (child:Model)-[:INHERITS]->(parent:Model)
RETURN child.name, parent.name
LIMIT 25
```

**Visualizar estructura de un módulo:**
```cypher
MATCH (mod:Module {name: "sale"})-[:CONTAINS]->(n)
RETURN mod, n
LIMIT 50
```

---

## 📈 Ver Estadísticas

### Módulos procesados:
```bash
jq 'length' output/modules.json
# Debería mostrar: 606
```

### Modelos encontrados:
```bash
jq 'length' output/models.json
```

### Vistas encontradas:
```bash
jq 'length' output/views.json
```

### Modelos por tipo:
```bash
jq '[.[] | .model_type] | group_by(.) | map({type: .[0], count: length})' output/models.json
```

### Top 10 módulos con más modelos:
```bash
jq 'group_by(.module) | map({module: .[0].module, count: length}) | sort_by(.count) | reverse | .[0:10]' output/models.json
```

### Top 10 módulos con más vistas:
```bash
jq 'group_by(.module) | map({module: .[0].module, count: length}) | sort_by(.count) | reverse | .[0:10]' output/views.json
```

---

## 🔥 Análisis Avanzados

### Encontrar todos los modelos que heredan de `mail.thread`:
```bash
jq '.[] | select(.inherits[] == "mail.thread") | .name' output/models.json
```

### Encontrar modelos sin descripción:
```bash
jq '.[] | select(.description == "") | {name: .name, module: .module}' output/models.json | head -n 10
```

### Encontrar modelos con muchos campos:
```bash
jq '.[] | {name: .name, fields: (.fields | length)} | select(.fields > 20)' output/models.json
```

### Listar todas las vistas de tipo "form":
```bash
jq '.[] | select(.view_type == "form") | .xml_id' output/views.json | head -n 20
```

---

## 🧹 Limpiar y Reiniciar

### Limpiar outputs:
```bash
rm -rf output/
rm -f .etl_state.db .test_etl_state.db
```

### Parar Neo4j:
```bash
docker stop neo4j-odoo
docker rm neo4j-odoo
```

### Limpiar todo y empezar de nuevo:
```bash
rm -rf output/ *.db
python quick_test.py
```

---

## 💡 Casos de Uso Reales

### 1. Auditar dependencias de un módulo:
```bash
# Ver qué modelos usa el módulo "sale"
jq '.[] | select(.module == "sale") | {name: .name, inherits: .inherits}' output/models.json
```

### 2. Encontrar vistas huérfanas (sin modelo):
```bash
jq '.[] | select(.model == "") | .xml_id' output/views.json
```

### 3. Análisis de complejidad por módulo:
```bash
# Módulos con más modelos = más complejos
jq 'group_by(.module) | map({
  module: .[0].module,
  models: length,
  total_fields: ([.[] | .fields | length] | add)
}) | sort_by(.models) | reverse | .[0:10]' output/models.json
```

### 4. Buscar patrones de herencia:
```bash
# Modelos que heredan de múltiples padres
jq '.[] | select(.inherits | length > 1) | {name: .name, inherits: .inherits}' output/models.json
```

---

## 🎓 Próximos Pasos

1. ✅ Ya probaste la extracción básica
2. 📊 Explora los JSON generados
3. 🗄️ (Opcional) Carga en Neo4j para queries avanzados
4. 🔧 Personaliza los scripts para tus necesidades
5. 📈 Crea dashboards o reportes con los datos

---

## ❓ ¿Problemas?

**Error: "No modules found"**
- Verifica la ruta: `ls ./odoo18/addons/*/`
- Debe contener carpetas con `__manifest__.py`

**Error: "ImportError: neo4j"**
- Solo si usas Neo4j: `pip install neo4j`
- Puedes ignorarlo si usas `--test-extract-only`

**Archivos JSON muy grandes:**
- Normal, Odoo tiene mucho código
- Usa `jq` para filtrar: `jq '.[0:10]' output/models.json`

---

## 🎉 ¡Listo!

Ya tienes un sistema completo funcionando que puede:
- ✅ Descubrir módulos de Odoo
- ✅ Extraer modelos Python con AST
- ✅ Parsear vistas XML
- ✅ Cargar en Neo4j (opcional)
- ✅ Hacer queries complejos
- ✅ Tracking incremental de cambios

**¡Empieza con `python quick_test.py` y explora!** 🚀

#!/bin/bash
# Script para descargar Odoo 18 para testing

set -e

ODOO_DIR="odoo18"
ODOO_BRANCH="18.0"
ODOO_REPO="https://github.com/odoo/odoo.git"

echo "========================================="
echo "Setup Odoo 18 para Testing"
echo "========================================="
echo ""

# Verificar si git está instalado
if ! command -v git &> /dev/null; then
    echo "Error: git no está instalado"
    exit 1
fi

echo "1. Clonando Odoo 18..."
echo "   Repositorio: $ODOO_REPO"
echo "   Rama: $ODOO_BRANCH"
echo "   Destino: ./$ODOO_DIR/"
echo ""

# Verificar si el directorio ya existe
if [ -d "$ODOO_DIR" ]; then
    echo "   El directorio $ODOO_DIR ya existe."
    read -p "   ¿Deseas eliminarlo y clonar de nuevo? (s/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "   Eliminando directorio existente..."
        rm -rf "$ODOO_DIR"
    else
        echo "   Usando directorio existente."
        cd "$ODOO_DIR"
        echo "   Actualizando repositorio..."
        git fetch origin
        git checkout "$ODOO_BRANCH"
        git pull origin "$ODOO_BRANCH"
        cd ..
        echo "   ✓ Repositorio actualizado"
        exit 0
    fi
fi

# Clonar solo la rama específica (shallow clone para ahorrar espacio)
echo "   Clonando... (esto puede tomar varios minutos)"
git clone --depth 1 --branch "$ODOO_BRANCH" "$ODOO_REPO" "$ODOO_DIR"

echo ""
echo "✓ Odoo 18 descargado exitosamente!"
echo ""

# Mostrar información
echo "========================================="
echo "Información de Odoo 18"
echo "========================================="
cd "$ODOO_DIR"
echo "Ruta completa: $(pwd)"
echo "Rama: $(git branch --show-current)"
echo "Último commit: $(git log -1 --oneline)"
echo ""

# Contar módulos
ADDONS_COUNT=$(find ./addons -maxdepth 1 -type d ! -name addons | wc -l)
ODOO_ADDONS_COUNT=$(find ./odoo/addons -maxdepth 1 -type d ! -name addons 2>/dev/null | wc -l || echo "0")

echo "Módulos encontrados:"
echo "  - ./addons: $ADDONS_COUNT módulos"
echo "  - ./odoo/addons: $ODOO_ADDONS_COUNT módulos"
echo ""

cd ..

# Crear archivo .env con rutas de Odoo
echo "========================================="
echo "Configuración"
echo "========================================="

if [ ! -f .env ]; then
    echo "Creando archivo .env..."
    cp .env.example .env
fi

# Actualizar rutas en .env
FULL_PATH="$(pwd)/$ODOO_DIR"
if grep -q "^ADDONS_PATHS=" .env; then
    # Actualizar línea existente
    sed -i.bak "s|^ADDONS_PATHS=.*|ADDONS_PATHS=$FULL_PATH/addons,$FULL_PATH/odoo/addons|" .env
    rm .env.bak 2>/dev/null || true
else
    # Agregar nueva línea
    echo "" >> .env
    echo "# Rutas de Odoo 18" >> .env
    echo "ADDONS_PATHS=$FULL_PATH/addons,$FULL_PATH/odoo/addons" >> .env
fi

echo "✓ Archivo .env actualizado con rutas de Odoo"
echo ""

echo "========================================="
echo "Próximos Pasos"
echo "========================================="
echo ""
echo "1. Verificar que Neo4j esté corriendo:"
echo "   $ docker-compose up -d"
echo ""
echo "2. Indexar módulos de Odoo 18:"
echo "   $ python main.py index $ODOO_DIR/addons --clear"
echo ""
echo "3. O indexar ambos directorios:"
echo "   $ python main.py index $ODOO_DIR/addons --clear"
echo "   $ python main.py index $ODOO_DIR/odoo/addons"
echo ""
echo "4. Probar comandos:"
echo "   $ python main.py find-model sale.order"
echo "   $ python main.py dependencies sale --recursive"
echo "   $ python main.py show-fields res.partner"
echo ""
echo "========================================="
echo "¡Listo para usar!"
echo "========================================="

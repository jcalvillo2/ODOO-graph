"""
Comandos CLI para la herramienta de tracking de dependencias de Odoo.
"""

import click
import os
from pathlib import Path
from typing import List
from rich.console import Console
from rich.tree import Tree
from rich.table import Table
from dotenv import load_dotenv

from ..parser import ManifestParser, ModelParser, ViewParser
from ..graph import Neo4jClient


# Cargar variables de entorno
load_dotenv()

console = Console()


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """
    Odoo Dependency Tracker - Herramienta para analizar dependencias de módulos Odoo.
    """
    pass


@cli.command()
@click.argument('addons_path', type=click.Path(exists=True))
@click.option('--clear', is_flag=True, help='Limpiar base de datos antes de indexar')
def index(addons_path: str, clear: bool):
    """
    Indexa módulos de Odoo desde un directorio de addons.

    ADDONS_PATH: Ruta al directorio de addons de Odoo
    """
    console.print(f"[bold blue]Indexando módulos desde:[/bold blue] {addons_path}")

    # Conectar a Neo4j
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            if clear:
                console.print("[yellow]Limpiando base de datos...[/yellow]")
                client.clear_database()

            # Escanear directorios
            addons_dir = Path(addons_path)
            modules = [d for d in addons_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]

            console.print(f"[green]Encontrados {len(modules)} módulos[/green]")

            indexed_modules = 0
            indexed_models = 0
            indexed_views = 0

            with console.status("[bold green]Indexando...") as status:
                for module_dir in modules:
                    # Buscar __manifest__.py
                    manifest_path = module_dir / '__manifest__.py'
                    if not manifest_path.exists():
                        # Intentar con __openerp__.py (versiones antiguas)
                        manifest_path = module_dir / '__openerp__.py'
                        if not manifest_path.exists():
                            continue

                    # Parsear manifest
                    manifest = ManifestParser.parse(str(manifest_path))
                    if not manifest:
                        continue

                    module_name = module_dir.name
                    status.update(f"[bold green]Indexando módulo: {module_name}")

                    # Crear nodo Module
                    client.create_module(
                        name=module_name,
                        version=manifest.get('version', ''),
                        category=manifest.get('category', ''),
                        summary=manifest.get('summary', ''),
                        author=manifest.get('author', ''),
                        installable=manifest.get('installable', True)
                    )
                    indexed_modules += 1

                    # Crear dependencias
                    depends = manifest.get('depends', [])
                    for dep in depends:
                        client.create_module_dependency(module_name, dep)

                    # Parsear modelos
                    models_dir = module_dir / 'models'
                    if models_dir.exists():
                        for py_file in models_dir.glob('*.py'):
                            if py_file.name == '__init__.py':
                                continue

                            models = ModelParser.parse_file(str(py_file))
                            for model_info in models:
                                # Crear nodo Model
                                client.create_model(
                                    name=model_info.name,
                                    module=module_name,
                                    file_path=str(py_file),
                                    fields=model_info.fields
                                )
                                indexed_models += 1

                                # Crear herencias
                                for parent in model_info.inherits_from:
                                    client.create_model_inheritance(model_info.name, parent)

                                # Crear delegaciones
                                for parent, field in model_info.delegates_to.items():
                                    client.create_model_delegation(model_info.name, parent, field)

                    # Parsear vistas XML
                    views_dir = module_dir / 'views'
                    if views_dir.exists():
                        for xml_file in views_dir.glob('*.xml'):
                            views = ViewParser.parse_file(str(xml_file))
                            for view_info in views:
                                # Crear nodo View
                                client.create_view(
                                    view_id=view_info.view_id,
                                    model=view_info.model,
                                    view_type=view_info.view_type,
                                    module=module_name,
                                    file_path=str(xml_file),
                                    name=view_info.name,
                                    priority=view_info.priority,
                                    mode=view_info.mode
                                )
                                indexed_views += 1

                                # Crear herencia de vistas
                                if view_info.inherit_id:
                                    client.create_view_inheritance(view_info.view_id, view_info.inherit_id)

            console.print(f"[bold green]Indexación completada![/bold green]")
            console.print(f"  Módulos indexados: {indexed_modules}")
            console.print(f"  Modelos indexados: {indexed_models}")
            console.print(f"  Vistas indexadas: {indexed_views}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('module_name')
@click.option('--recursive', '-r', is_flag=True, help='Mostrar dependencias recursivas')
def dependencies(module_name: str, recursive: bool):
    """
    Muestra las dependencias de un módulo.

    MODULE_NAME: Nombre del módulo (ej: sale, stock)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            deps = client.get_module_dependencies(module_name, recursive=recursive)

            if not deps:
                console.print(f"[yellow]Módulo '{module_name}' no tiene dependencias o no existe[/yellow]")
                return

            tree = Tree(f"[bold blue]{module_name}[/bold blue]")
            for dep in deps:
                tree.add(f"[green]{dep}[/green]")

            console.print(tree)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('model_name')
def find_model(model_name: str):
    """
    Encuentra en qué módulo está definido un modelo.

    MODEL_NAME: Nombre del modelo (ej: sale.order, res.partner)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            model = client.find_model(model_name)

            if not model:
                console.print(f"[yellow]Modelo '{model_name}' no encontrado[/yellow]")
                return

            console.print(f"[bold]Modelo:[/bold] {model['name']}")
            console.print(f"[bold]Definido en:[/bold] módulo '{model['module']}'")
            console.print(f"[bold]Archivo:[/bold] {model['file_path']}")

            # Mostrar herencia
            parents = client.get_model_inheritance(model_name)
            if parents:
                console.print(f"[bold]Hereda de:[/bold] {', '.join(parents)}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('model_name')
def show_fields(model_name: str):
    """
    Muestra los campos de un modelo.

    MODEL_NAME: Nombre del modelo (ej: sale.order)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            model = client.find_model(model_name)

            if not model:
                console.print(f"[yellow]Modelo '{model_name}' no encontrado[/yellow]")
                return

            fields = model.get('fields', {})
            if not fields:
                console.print(f"[yellow]Modelo '{model_name}' no tiene campos registrados[/yellow]")
                return

            table = Table(title=f"Campos de {model_name}")
            table.add_column("Campo", style="cyan")
            table.add_column("Tipo", style="green")
            table.add_column("Relación", style="magenta")
            table.add_column("Info", style="yellow")

            for field_name, field_info in fields.items():
                field_type = field_info.get('type', '')
                relation = field_info.get('relation', '')
                string = field_info.get('string', '')

                table.add_row(field_name, field_type, relation, string)

            console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('field_name')
def find_field(field_name: str):
    """
    Busca un campo en todos los modelos.

    FIELD_NAME: Nombre del campo (ej: partner_id, name)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            matches = client.find_field_in_models(field_name)

            if not matches:
                console.print(f"[yellow]Campo '{field_name}' no encontrado en ningún modelo[/yellow]")
                return

            console.print(f"[bold]Campo '{field_name}' encontrado en {len(matches)} modelo(s):[/bold]\n")

            for match in matches:
                field_info = match['field_info']
                field_type = field_info.get('type', '')
                relation = field_info.get('relation', '')

                console.print(f"  [cyan]{match['model']}[/cyan] ([yellow]{match['module']}[/yellow]): ", end='')
                if relation:
                    console.print(f"[green]{field_type}[/green]([magenta]'{relation}'[/magenta])")
                else:
                    console.print(f"[green]{field_type}[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('module_name')
def list_models(module_name: str):
    """
    Lista todos los modelos de un módulo.

    MODULE_NAME: Nombre del módulo (ej: sale, stock)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            models = client.list_models_in_module(module_name)

            if not models:
                console.print(f"[yellow]Módulo '{module_name}' no tiene modelos o no existe[/yellow]")
                return

            console.print(f"[bold]Modelos en '{module_name}':[/bold]\n")
            for model in models:
                console.print(f"  [cyan]{model}[/cyan]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


# ===== COMANDOS DE VISTAS =====

@cli.command()
@click.argument('model_name')
def find_views(model_name: str):
    """
    Busca todas las vistas de un modelo.

    MODEL_NAME: Nombre del modelo (ej: sale.order, res.partner)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            views = client.find_views_by_model(model_name)

            if not views:
                console.print(f"[yellow]No se encontraron vistas para el modelo '{model_name}'[/yellow]")
                return

            console.print(f"[bold]Vistas para '{model_name}':[/bold]\n")

            # Agrupar por tipo
            views_by_type = {}
            for view in views:
                view_type = view['type']
                if view_type not in views_by_type:
                    views_by_type[view_type] = []
                views_by_type[view_type].append(view)

            # Mostrar agrupadas
            for view_type in sorted(views_by_type.keys()):
                console.print(f"  [bold cyan]{view_type.upper()}:[/bold cyan]")
                for view in views_by_type[view_type]:
                    console.print(f"    - {view['id']} ([yellow]{view['module']}[/yellow])")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('view_id')
def view_inheritance(view_id: str):
    """
    Muestra el árbol de herencia de una vista.

    VIEW_ID: ID de la vista (ej: view_sale_order_form)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            children = client.find_view_inheritance(view_id)

            if not children:
                console.print(f"[yellow]Vista '{view_id}' no tiene vistas que la hereden[/yellow]")
                return

            console.print(f"[bold]Vista '{view_id}' es heredada por:[/bold]\n")

            tree = Tree(f"[bold blue]{view_id}[/bold blue]")
            for child in children:
                tree.add(f"[green]{child}[/green]")

            console.print(tree)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


@cli.command()
@click.argument('module_name')
def list_views(module_name: str):
    """
    Lista todas las vistas de un módulo.

    MODULE_NAME: Nombre del módulo (ej: sale, stock)
    """
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'your-password-here')

    try:
        with Neo4jClient(uri, user, password) as client:
            views = client.list_views_in_module(module_name)

            if not views:
                console.print(f"[yellow]Módulo '{module_name}' no tiene vistas o no existe[/yellow]")
                return

            console.print(f"[bold]Vistas en módulo '{module_name}':[/bold]\n")

            # Agrupar por modelo
            views_by_model = {}
            for view in views:
                model = view['model']
                if model not in views_by_model:
                    views_by_model[model] = []
                views_by_model[model].append(view)

            # Mostrar agrupadas por modelo
            for model in sorted(views_by_model.keys()):
                console.print(f"  [bold cyan]{model}:[/bold cyan]")
                for view in views_by_model[model]:
                    console.print(f"    - {view['id']} ([magenta]{view['type']}[/magenta])")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == '__main__':
    cli()

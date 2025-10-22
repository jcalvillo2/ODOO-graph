#!/usr/bin/env python3
"""
Odoo Tracker - Main CLI Entry Point

A tool for analyzing, tracking, and visualizing Odoo module dependencies,
models, and views using a Neo4j graph database.
"""

import sys

import click
from rich.console import Console

from config import get_settings
from utils import setup_logger

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="odoo-tracker")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Set logging level",
)
def cli(log_level):
    """
    Odoo Tracker - Analyze and track Odoo module dependencies.

    This tool indexes Odoo modules, models, and views into a Neo4j graph
    database, enabling powerful queries and dependency analysis.
    """
    # Load settings
    settings = get_settings()

    # Override log level if provided
    if log_level:
        settings.log_level = log_level

    # Setup logging
    setup_logger(
        name="odoo_tracker",
        level=settings.log_level,
        log_file=settings.log_file,
    )


@cli.command()
def config():
    """Show current configuration."""
    settings = get_settings()

    console.print("\n[bold cyan]Odoo Tracker Configuration[/bold cyan]\n")

    config_dict = settings.to_dict()

    # Don't show password in output
    if "neo4j_password" in config_dict:
        config_dict["neo4j_password"] = "***"

    for key, value in config_dict.items():
        console.print(f"[yellow]{key}[/yellow]: {value}")

    console.print()


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--batch-size",
    type=int,
    help="Number of items to process in each batch",
)
@click.option(
    "--incremental",
    is_flag=True,
    help="Only index files that have changed (based on file hash)",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Clear existing data before indexing",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt when clearing data",
)
def index(path, batch_size, incremental, clear, yes):
    """
    Index Odoo modules from a directory.

    PATH: Directory containing Odoo modules to index
    """
    from pathlib import Path
    from graph import Neo4jConnection, OdooIndexer
    from utils.logger import get_logger

    logger = get_logger(__name__)

    console.print("\n[bold cyan]=" * 40 + "[/bold cyan]")
    console.print("[bold cyan]Odoo Tracker - Indexing Process[/bold cyan]")
    console.print("[bold cyan]=" * 40 + "[/bold cyan]\n")

    settings = get_settings()

    # Override batch size if provided
    if batch_size:
        settings.batch_size = batch_size

    # Display configuration
    console.print(f"[yellow]Source path:[/yellow] {path}")
    console.print(f"[yellow]Neo4j URI:[/yellow] {settings.neo4j_uri}")
    console.print(f"[yellow]Batch size:[/yellow] {settings.batch_size}")
    console.print(f"[yellow]Max memory:[/yellow] {settings.max_memory_percent}%")
    console.print(f"[yellow]Incremental:[/yellow] {incremental}")
    console.print(f"[yellow]Clear existing:[/yellow] {clear}\n")

    if clear and not yes:
        console.print("[bold red]WARNING:[/bold red] This will delete all existing data!")
        if not click.confirm("Are you sure you want to continue?"):
            console.print("[yellow]Aborted[/yellow]\n")
            return

    try:
        # Connect to Neo4j
        console.print("[cyan]Connecting to Neo4j...[/cyan]")
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            max_retries=3,
            retry_delay=1.0
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings and ensure Neo4j is running.\n")
            sys.exit(1)

        console.print("[green]✓ Connected to Neo4j[/green]\n")

        # Create indexer
        indexer = OdooIndexer(
            odoo_path=Path(path),
            connection=connection,
            batch_size=settings.batch_size,
            max_memory_percent=settings.max_memory_percent
        )

        # Run indexing
        console.print("[bold cyan]Starting indexing process...[/bold cyan]\n")

        stats = indexer.index_all(
            clear_existing=clear,
            incremental=incremental
        )

        # Display results
        console.print("\n[bold cyan]=" * 40 + "[/bold cyan]")
        console.print("[bold green]Indexing Completed Successfully![/bold green]")
        console.print("[bold cyan]=" * 40 + "[/bold cyan]\n")

        console.print(f"[yellow]Duration:[/yellow] {stats['duration_seconds']:.2f} seconds")
        console.print(f"[yellow]Modules found:[/yellow] {stats['modules_found']}")
        console.print(f"[yellow]Modules indexed:[/yellow] {stats['modules_indexed']}")
        console.print(f"[yellow]Models indexed:[/yellow] {stats['models_indexed']}")
        console.print(f"[yellow]Fields indexed:[/yellow] {stats['fields_indexed']}")
        console.print(f"[yellow]Relationships created:[/yellow] {stats['relationships_created']}")

        if stats['errors'] > 0:
            console.print(f"[red]Errors:[/red] {stats['errors']}")

        # Display database statistics
        if 'db_stats' in stats:
            console.print("\n[bold cyan]Database Statistics:[/bold cyan]")
            db_stats = stats['db_stats']
            console.print(f"[yellow]Total modules:[/yellow] {db_stats.get('module_count', 0)}")
            console.print(f"[yellow]Total models:[/yellow] {db_stats.get('model_count', 0)}")
            console.print(f"[yellow]Total fields:[/yellow] {db_stats.get('field_count', 0)}")
            console.print(f"[yellow]Dependencies:[/yellow] {db_stats.get('depends_on_count', 0)}")
            console.print(f"[yellow]Inheritance:[/yellow] {db_stats.get('inherits_from_count', 0)}")

        console.print()

        # Close connection
        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error during indexing:[/bold red] {str(e)}\n")
        logger.error(f"Indexing failed: {str(e)}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("module_name")
@click.option("--reverse", is_flag=True, help="Show modules that depend on this module")
def dependencies(module_name, reverse):
    """
    Show dependencies for a module.

    MODULE_NAME: Name of the module to analyze
    """
    from rich.table import Table
    from graph import Neo4jConnection
    from graph.queries import get_module_dependencies, get_module_dependents
    from utils.logger import get_logger

    logger = get_logger(__name__)
    settings = get_settings()

    console.print(f"\n[bold cyan]{'Reverse dependencies' if reverse else 'Dependencies'} for module:[/bold cyan] [yellow]{module_name}[/yellow]\n")

    try:
        # Connect to Neo4j
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings.\n")
            sys.exit(1)

        # Get dependencies or dependents
        if reverse:
            query, params = get_module_dependents(module_name)
            results = connection.execute_query(query, params)

            if not results:
                console.print(f"[yellow]No modules depend on '{module_name}'[/yellow]\n")
                connection.close()
                return

            table = Table(title=f"Modules that depend on {module_name}")
            table.add_column("Module", style="cyan")
            table.add_column("Version", style="yellow")
            table.add_column("Category", style="green")

            for dep in results:
                table.add_row(
                    dep.get('dependent', ''),
                    dep.get('version', ''),
                    dep.get('category', '')
                )
        else:
            query, params = get_module_dependencies(module_name)
            results = connection.execute_query(query, params)

            if not results:
                console.print(f"[yellow]Module '{module_name}' has no dependencies[/yellow]\n")
                connection.close()
                return

            table = Table(title=f"Dependencies of {module_name}")
            table.add_column("Dependency", style="cyan")
            table.add_column("Version", style="yellow")
            table.add_column("Category", style="green")

            for dep in results:
                table.add_row(
                    dep.get('dependency', ''),
                    dep.get('version', ''),
                    dep.get('category', '')
                )

        console.print(table)
        console.print()

        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Dependencies query failed: {str(e)}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("model_name")
@click.option("--fields", is_flag=True, help="Show model fields")
@click.option("--limit", default=20, help="Limit number of fields shown")
def find_model(model_name, fields, limit):
    """
    Find where a model is defined.

    MODEL_NAME: Technical name of the model (e.g., 'sale.order')
    """
    from rich.table import Table
    from rich.panel import Panel
    from graph import Neo4jConnection
    from graph.queries import find_model_by_name, get_model_fields
    from utils.logger import get_logger

    logger = get_logger(__name__)
    settings = get_settings()

    console.print(f"\n[bold cyan]Searching for model:[/bold cyan] [yellow]{model_name}[/yellow]\n")

    try:
        # Connect to Neo4j
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings.\n")
            sys.exit(1)

        # Find the model
        query, params = find_model_by_name(model_name)
        results = connection.execute_query(query, params)

        if not results:
            console.print(f"[yellow]Model '{model_name}' not found[/yellow]\n")
            connection.close()
            return

        # Display all definitions (base + extensions)
        if len(results) > 1:
            console.print(f"[yellow]Found {len(results)} definitions of this model (base + extensions)[/yellow]\n")

        for idx, result in enumerate(results, 1):
            model = result.get('model', {})
            module_name = result.get('module_name', 'Unknown')
            is_base = idx == 1  # First result is the base/core definition

            # Display model info
            title_suffix = " (BASE)" if is_base else f" (Extension {idx-1})"
            info_text = f"""
[bold]Model:[/bold] {model.get('name', 'N/A')}
[bold]Description:[/bold] {model.get('description', 'N/A') or 'N/A'}
[bold]Module:[/bold] {module_name}
[bold]Class:[/bold] {model.get('class_name', 'N/A')}
[bold]File:[/bold] {model.get('file_path', 'N/A')}
[bold]Line:[/bold] {model.get('line_number', 'N/A')}
"""
            border_color = "green" if is_base else "yellow"
            panel = Panel(info_text.strip(), title=f"Model: {model_name}{title_suffix}", border_style=border_color)
            console.print(panel)

        console.print()

        # Show fields if requested
        if fields:
            query, params = get_model_fields(model_name)
            field_results = connection.execute_query(query, params)

            if field_results:
                table = Table(title=f"Fields of {model_name} (showing {min(limit, len(field_results))} of {len(field_results)})")
                table.add_column("Field", style="cyan")
                table.add_column("Type", style="yellow")
                table.add_column("Label", style="green")
                table.add_column("Required", style="magenta")
                table.add_column("Comodel", style="blue")

                for field in field_results[:limit]:
                    table.add_row(
                        field.get('name', ''),
                        field.get('type', ''),
                        (field.get('string', '') or '')[:40],
                        "✓" if field.get('required') else "",
                        field.get('comodel_name', '') or ''
                    )

                console.print(table)
                console.print()

        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Find model query failed: {str(e)}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("module_name")
def list_models(module_name):
    """
    List all models defined in a module.

    MODULE_NAME: Name of the module
    """
    from rich.table import Table
    from graph import Neo4jConnection
    from graph.queries import list_models_in_module
    from utils.logger import get_logger

    logger = get_logger(__name__)
    settings = get_settings()

    console.print(f"\n[bold cyan]Models in module:[/bold cyan] [yellow]{module_name}[/yellow]\n")

    try:
        # Connect to Neo4j
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings.\n")
            sys.exit(1)

        # Get models in module
        query, params = list_models_in_module(module_name)
        results = connection.execute_query(query, params)

        if not results:
            console.print(f"[yellow]No models found in module '{module_name}'[/yellow]\n")
            connection.close()
            return

        table = Table(title=f"Models in {module_name} ({len(results)} total)")
        table.add_column("Model", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("File", style="yellow")

        for model in results:
            file_path = model.get('file_path', '')
            # Show only the filename, not full path
            filename = file_path.split('/')[-1] if file_path else ''

            table.add_row(
                model.get('name', ''),
                (model.get('description', '') or '')[:50],
                filename
            )

        console.print(table)
        console.print()

        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"List models query failed: {str(e)}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("model_name")
@click.option("--depth", default=5, help="Maximum inheritance depth to show")
def inheritance(model_name, depth):
    """
    Show inheritance tree for a model.

    MODEL_NAME: Technical name of the model (e.g., 'sale.order')
    """
    from rich.table import Table
    from rich.tree import Tree
    from graph import Neo4jConnection
    from graph.queries import get_model_inheritance_tree, get_model_children
    from utils.logger import get_logger

    logger = get_logger(__name__)
    settings = get_settings()

    console.print(f"\n[bold cyan]Inheritance tree for model:[/bold cyan] [yellow]{model_name}[/yellow]\n")

    try:
        # Connect to Neo4j
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings.\n")
            sys.exit(1)

        # Get parent inheritance
        query, params = get_model_inheritance_tree(model_name, depth)
        parent_results = connection.execute_query(query, params)

        # Get children
        query, params = get_model_children(model_name)
        children_results = connection.execute_query(query, params)

        # Display parents
        if parent_results:
            table = Table(title=f"Parents of {model_name}")
            table.add_column("Parent Model", style="cyan")
            table.add_column("Depth", style="yellow")

            for result in parent_results:
                if result.get('parent') and result.get('parent') != model_name:
                    table.add_row(
                        result.get('parent', ''),
                        str(result.get('depth', 0))
                    )

            if table.row_count > 0:
                console.print(table)
                console.print()

        # Display children
        if children_results:
            table = Table(title=f"Children of {model_name}")
            table.add_column("Child Model", style="green")
            table.add_column("Description", style="yellow")

            for result in children_results:
                table.add_row(
                    result.get('child', ''),
                    (result.get('description', '') or '')[:50]
                )

            console.print(table)
            console.print()

        if not parent_results and not children_results:
            console.print(f"[yellow]No inheritance relationships found for '{model_name}'[/yellow]\n")

        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Inheritance query failed: {str(e)}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("field_name")
@click.option("--model", help="Filter by model name")
@click.option("--limit", default=20, help="Limit number of results")
def find_field(field_name, model, limit):
    """
    Find fields by name across all models.

    FIELD_NAME: Name of the field to search for
    """
    from rich.table import Table
    from graph import Neo4jConnection
    from graph.queries import find_field_by_name
    from utils.logger import get_logger

    logger = get_logger(__name__)
    settings = get_settings()

    console.print(f"\n[bold cyan]Searching for field:[/bold cyan] [yellow]{field_name}[/yellow]")
    if model:
        console.print(f"[bold cyan]In model:[/bold cyan] [yellow]{model}[/yellow]")
    console.print()

    try:
        # Connect to Neo4j
        connection = Neo4jConnection(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )

        if not connection.connect():
            console.print("[bold red]Failed to connect to Neo4j[/bold red]")
            console.print("Please check your connection settings.\n")
            sys.exit(1)

        # Find fields
        query, params = find_field_by_name(field_name, model)
        results = connection.execute_query(query, params)

        if not results:
            console.print(f"[yellow]Field '{field_name}' not found[/yellow]\n")
            connection.close()
            return

        table = Table(title=f"Field '{field_name}' found in {len(results)} model(s) (showing {min(limit, len(results))})")
        table.add_column("Model", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Label", style="green")
        table.add_column("Required", style="magenta")

        for result in results[:limit]:
            table.add_row(
                result.get('model', ''),
                result.get('type', ''),
                (result.get('string', '') or '')[:40],
                "✓" if result.get('required') else ""
            )

        console.print(table)
        console.print()

        connection.close()

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Find field query failed: {str(e)}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

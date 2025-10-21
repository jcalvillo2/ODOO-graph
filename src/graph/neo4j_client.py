"""
Cliente Neo4j para gestionar el grafo de dependencias de Odoo.
"""

from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase, Driver
import json
import os


class Neo4jClient:
    """
    Cliente para interactuar con Neo4j y almacenar/consultar
    el grafo de dependencias de módulos y modelos de Odoo.
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Inicializa la conexión con Neo4j.

        Args:
            uri: URI de conexión (ej: bolt://localhost:7687)
            user: Usuario de Neo4j
            password: Contraseña
        """
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Cierra la conexión con Neo4j."""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def clear_database(self):
        """Elimina todos los nodos y relaciones de la base de datos."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def create_module(self, name: str, **properties) -> None:
        """
        Crea un nodo Module.

        Args:
            name: Nombre del módulo
            **properties: Propiedades adicionales (version, category, etc.)
        """
        with self.driver.session() as session:
            query = """
            MERGE (m:Module {name: $name})
            SET m += $properties
            """
            props = {'name': name, **properties}
            session.run(query, name=name, properties=props)

    def create_model(self, name: str, module: str, file_path: str, fields: Dict = None) -> None:
        """
        Crea un nodo Model y su relación DEFINED_IN con el módulo.

        Args:
            name: Nombre del modelo (ej: 'sale.order')
            module: Nombre del módulo donde está definido
            file_path: Ruta al archivo .py
            fields: Diccionario de campos del modelo
        """
        with self.driver.session() as session:
            # Convertir fields a JSON string para Neo4j
            fields_json = json.dumps(fields) if fields else "{}"

            query = """
            MERGE (model:Model {name: $name})
            SET model.module = $module,
                model.file_path = $file_path,
                model.fields_json = $fields_json
            WITH model
            MATCH (m:Module {name: $module})
            MERGE (model)-[:DEFINED_IN]->(m)
            """
            session.run(
                query,
                name=name,
                module=module,
                file_path=file_path,
                fields_json=fields_json
            )

    def create_module_dependency(self, from_module: str, to_module: str) -> None:
        """
        Crea una relación DEPENDS_ON entre módulos.
        Solo crea la relación si ambos módulos ya existen en la BD.

        Args:
            from_module: Módulo que depende
            to_module: Módulo del que depende
        """
        with self.driver.session() as session:
            query = """
            MATCH (from:Module {name: $from_module})
            MATCH (to:Module {name: $to_module})
            MERGE (from)-[:DEPENDS_ON]->(to)
            """
            session.run(query, from_module=from_module, to_module=to_module)

    def create_model_inheritance(self, from_model: str, to_model: str) -> None:
        """
        Crea una relación INHERITS_FROM entre modelos.

        Args:
            from_model: Modelo que hereda
            to_model: Modelo del que hereda
        """
        with self.driver.session() as session:
            query = """
            MERGE (from:Model {name: $from_model})
            MERGE (to:Model {name: $to_model})
            MERGE (from)-[:INHERITS_FROM]->(to)
            """
            session.run(query, from_model=from_model, to_model=to_model)

    def create_model_delegation(self, from_model: str, to_model: str, field: str) -> None:
        """
        Crea una relación DELEGATES_TO entre modelos (_inherits).

        Args:
            from_model: Modelo que delega
            to_model: Modelo al que delega
            field: Campo de delegación
        """
        with self.driver.session() as session:
            query = """
            MERGE (from:Model {name: $from_model})
            MERGE (to:Model {name: $to_model})
            MERGE (from)-[:DELEGATES_TO {field: $field}]->(to)
            """
            session.run(query, from_model=from_model, to_model=to_model, field=field)

    def get_module_dependencies(self, module_name: str, recursive: bool = False) -> List[str]:
        """
        Obtiene las dependencias de un módulo.

        Args:
            module_name: Nombre del módulo
            recursive: Si True, obtiene dependencias recursivas

        Returns:
            Lista de nombres de módulos de los que depende
        """
        with self.driver.session() as session:
            if recursive:
                query = """
                MATCH path = (m:Module {name: $name})-[:DEPENDS_ON*]->(dep)
                RETURN DISTINCT dep.name as dependency
                """
            else:
                query = """
                MATCH (m:Module {name: $name})-[:DEPENDS_ON]->(dep)
                RETURN dep.name as dependency
                """

            result = session.run(query, name=module_name)
            return [record['dependency'] for record in result]

    def find_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca información de un modelo.

        Args:
            model_name: Nombre del modelo (ej: 'sale.order')

        Returns:
            Diccionario con información del modelo o None si no existe
        """
        with self.driver.session() as session:
            query = """
            MATCH (model:Model {name: $name})-[:DEFINED_IN]->(m:Module)
            RETURN model.name as name,
                   model.file_path as file_path,
                   model.fields_json as fields_json,
                   m.name as module
            """
            result = session.run(query, name=model_name)
            record = result.single()

            if record:
                # Deserializar JSON de fields
                fields = json.loads(record['fields_json']) if record['fields_json'] else {}
                return {
                    'name': record['name'],
                    'module': record['module'],
                    'file_path': record['file_path'],
                    'fields': fields
                }
            return None

    def get_model_inheritance(self, model_name: str) -> List[str]:
        """
        Obtiene los modelos de los que hereda un modelo.

        Args:
            model_name: Nombre del modelo

        Returns:
            Lista de nombres de modelos padre
        """
        with self.driver.session() as session:
            query = """
            MATCH (m:Model {name: $name})-[:INHERITS_FROM]->(parent)
            RETURN parent.name as parent_name
            """
            result = session.run(query, name=model_name)
            return [record['parent_name'] for record in result]

    def find_field_in_models(self, field_name: str) -> List[Dict[str, Any]]:
        """
        Busca un campo en todos los modelos.

        Args:
            field_name: Nombre del campo a buscar

        Returns:
            Lista de diccionarios con modelo, tipo de campo, etc.
        """
        with self.driver.session() as session:
            query = """
            MATCH (model:Model)
            WHERE model.fields_json IS NOT NULL
            RETURN model.name as model_name,
                   model.module as module,
                   model.fields_json as fields_json
            """
            result = session.run(query)
            matches = []

            for record in result:
                # Deserializar JSON
                fields = json.loads(record['fields_json']) if record['fields_json'] else {}
                if fields and field_name in fields:
                    matches.append({
                        'model': record['model_name'],
                        'module': record['module'],
                        'field_info': fields[field_name]
                    })

            return matches

    def list_models_in_module(self, module_name: str) -> List[str]:
        """
        Lista todos los modelos definidos en un módulo.

        Args:
            module_name: Nombre del módulo

        Returns:
            Lista de nombres de modelos
        """
        with self.driver.session() as session:
            query = """
            MATCH (model:Model)-[:DEFINED_IN]->(m:Module {name: $name})
            RETURN model.name as model_name
            ORDER BY model_name
            """
            result = session.run(query, name=module_name)
            return [record['model_name'] for record in result]

    # ===== VIEW METHODS =====

    def create_view(self, view_id: str, model: str, view_type: str, module: str,
                   file_path: str, **properties) -> None:
        """
        Crea un nodo View y sus relaciones.

        Args:
            view_id: ID de la vista (ej: 'view_sale_order_form')
            model: Modelo al que pertenece (ej: 'sale.order')
            view_type: Tipo de vista (form, tree, kanban, etc.)
            module: Módulo donde está definida
            file_path: Ruta al archivo XML
            **properties: Propiedades adicionales (name, priority, mode, etc.)
        """
        with self.driver.session() as session:
            query = """
            MERGE (v:View {id: $view_id})
            SET v.model = $model,
                v.type = $view_type,
                v.module = $module,
                v.file_path = $file_path,
                v += $properties
            WITH v
            MERGE (m:Model {name: $model})
            MERGE (v)-[:BELONGS_TO]->(m)
            WITH v
            MATCH (mod:Module {name: $module})
            MERGE (v)-[:DEFINED_IN]->(mod)
            """
            session.run(
                query,
                view_id=view_id,
                model=model,
                view_type=view_type,
                module=module,
                file_path=file_path,
                properties=properties
            )

    def create_view_inheritance(self, child_view_id: str, parent_view_id: str) -> None:
        """
        Crea una relación INHERITS_VIEW entre vistas.

        Args:
            child_view_id: Vista que hereda
            parent_view_id: Vista de la que hereda
        """
        with self.driver.session() as session:
            query = """
            MERGE (child:View {id: $child_id})
            MERGE (parent:View {id: $parent_id})
            MERGE (child)-[:INHERITS_VIEW]->(parent)
            """
            session.run(query, child_id=child_view_id, parent_id=parent_view_id)

    def find_views_by_model(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Busca todas las vistas de un modelo.

        Args:
            model_name: Nombre del modelo (ej: 'sale.order')

        Returns:
            Lista de diccionarios con información de vistas
        """
        with self.driver.session() as session:
            query = """
            MATCH (v:View)-[:BELONGS_TO]->(m:Model {name: $model})
            RETURN v.id as id,
                   v.type as type,
                   v.module as module,
                   v.name as name,
                   v.file_path as file_path
            ORDER BY v.type, v.id
            """
            result = session.run(query, model=model_name)
            return [
                {
                    'id': record['id'],
                    'type': record['type'],
                    'module': record['module'],
                    'name': record['name'],
                    'file_path': record['file_path']
                }
                for record in result
            ]

    def find_view_inheritance(self, view_id: str) -> List[str]:
        """
        Obtiene el árbol de herencia de una vista.

        Args:
            view_id: ID de la vista

        Returns:
            Lista de IDs de vistas que heredan de esta
        """
        with self.driver.session() as session:
            query = """
            MATCH (child:View)-[:INHERITS_VIEW]->(parent:View {id: $view_id})
            RETURN child.id as child_id
            ORDER BY child_id
            """
            result = session.run(query, view_id=view_id)
            return [record['child_id'] for record in result]

    def list_views_in_module(self, module_name: str) -> List[Dict[str, Any]]:
        """
        Lista todas las vistas definidas en un módulo.

        Args:
            module_name: Nombre del módulo

        Returns:
            Lista de diccionarios con información de vistas agrupadas por modelo
        """
        with self.driver.session() as session:
            query = """
            MATCH (v:View)-[:DEFINED_IN]->(m:Module {name: $name})
            RETURN v.id as id,
                   v.model as model,
                   v.type as type,
                   v.name as name
            ORDER BY v.model, v.type, v.id
            """
            result = session.run(query, name=module_name)
            return [
                {
                    'id': record['id'],
                    'model': record['model'],
                    'type': record['type'],
                    'name': record['name']
                }
                for record in result
            ]

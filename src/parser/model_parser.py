"""
Parser AST para modelos de Odoo.
"""

import ast
import os
from typing import Dict, List, Optional, Any


class ModelInfo:
    """Representa información de un modelo Odoo."""

    def __init__(self, name: str, file_path: str):
        self.name = name
        self.file_path = file_path
        self.inherits_from: List[str] = []
        self.delegates_to: Dict[str, str] = {}  # {model: field}
        self.fields: Dict[str, Dict[str, Any]] = {}

    def __repr__(self):
        return f"ModelInfo(name={self.name}, inherits={self.inherits_from})"


class ModelParser:
    """
    Parser AST para extraer modelos de archivos Python de Odoo.
    """

    @staticmethod
    def parse_file(file_path: str) -> List[ModelInfo]:
        """
        Parsea un archivo Python y extrae todos los modelos Odoo.

        Args:
            file_path: Ruta al archivo .py

        Returns:
            Lista de ModelInfo encontrados
        """
        if not os.path.exists(file_path):
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            models = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    model_info = ModelParser._extract_model_info(node, file_path)
                    if model_info:
                        models.append(model_info)

            return models

        except Exception as e:
            print(f"Error parseando {file_path}: {e}")
            return []

    @staticmethod
    def _extract_model_info(class_node: ast.ClassDef, file_path: str) -> Optional[ModelInfo]:
        """
        Extrae información de un nodo de clase que podría ser un modelo Odoo.

        Args:
            class_node: Nodo AST ClassDef
            file_path: Ruta del archivo

        Returns:
            ModelInfo si es un modelo Odoo, None en caso contrario
        """
        model_name = None
        inherits_from = []
        delegates_to = {}
        fields = {}

        # Recorrer el cuerpo de la clase
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id

                        # Buscar _name
                        if attr_name == '_name':
                            model_name = ModelParser._extract_string(item.value)

                        # Buscar _inherit
                        elif attr_name == '_inherit':
                            inherits_from = ModelParser._extract_inherit(item.value)

                        # Buscar _inherits (delegación)
                        elif attr_name == '_inherits':
                            delegates_to = ModelParser._extract_inherits(item.value)

                        # Buscar campos (fields.Char, fields.Many2one, etc.)
                        elif ModelParser._is_field(item.value):
                            field_info = ModelParser._extract_field_info(item.value)
                            if field_info:
                                fields[attr_name] = field_info

        # Si no hay _name pero hay _inherit, usar el primero de _inherit como nombre
        if not model_name and inherits_from:
            model_name = inherits_from[0] if isinstance(inherits_from, list) else inherits_from

        # Si no es un modelo Odoo, retornar None
        if not model_name:
            return None

        model_info = ModelInfo(model_name, file_path)
        model_info.inherits_from = inherits_from if isinstance(inherits_from, list) else [inherits_from] if inherits_from else []
        model_info.delegates_to = delegates_to
        model_info.fields = fields

        return model_info

    @staticmethod
    def _extract_string(node: ast.AST) -> Optional[str]:
        """Extrae un string de un nodo AST."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        elif isinstance(node, ast.Str):
            return node.s
        return None

    @staticmethod
    def _extract_inherit(node: ast.AST) -> List[str]:
        """Extrae valores de _inherit (puede ser string o lista)."""
        if isinstance(node, (ast.Constant, ast.Str)):
            value = ModelParser._extract_string(node)
            return [value] if value else []
        elif isinstance(node, ast.List):
            result = []
            for item in node.elts:
                value = ModelParser._extract_string(item)
                if value:
                    result.append(value)
            return result
        return []

    @staticmethod
    def _extract_inherits(node: ast.AST) -> Dict[str, str]:
        """Extrae valores de _inherits (diccionario {model: field})."""
        if not isinstance(node, ast.Dict):
            return {}

        result = {}
        for key, value in zip(node.keys, node.values):
            model = ModelParser._extract_string(key)
            field = ModelParser._extract_string(value)
            if model and field:
                result[model] = field

        return result

    @staticmethod
    def _is_field(node: ast.AST) -> bool:
        """Determina si un nodo es un campo de Odoo (fields.Char, etc.)."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    return node.func.value.id == 'fields'
        return False

    @staticmethod
    def _extract_field_info(node: ast.Call) -> Optional[Dict[str, Any]]:
        """Extrae información de un campo Odoo."""
        if not isinstance(node.func, ast.Attribute):
            return None

        field_type = node.func.attr
        info = {'type': field_type}

        # Extraer primer argumento (relación para Many2one, One2many, etc.)
        if node.args:
            first_arg = ModelParser._extract_string(node.args[0])
            if first_arg:
                info['relation'] = first_arg

        # Extraer argumentos con nombre (string, required, etc.)
        for keyword in node.keywords:
            if keyword.arg == 'string':
                info['string'] = ModelParser._extract_string(keyword.value)
            elif keyword.arg == 'required':
                info['required'] = True
            elif keyword.arg == 'compute':
                info['compute'] = ModelParser._extract_string(keyword.value)

        return info

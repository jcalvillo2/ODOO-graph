"""
Parser para archivos __manifest__.py de módulos Odoo.
"""

import ast
import os
from typing import Dict, Any, Optional


class ManifestParser:
    """
    Parser para extraer información de archivos __manifest__.py.
    """

    @staticmethod
    def parse(manifest_path: str) -> Optional[Dict[str, Any]]:
        """
        Parsea un archivo __manifest__.py y extrae sus metadatos.

        Args:
            manifest_path: Ruta al archivo __manifest__.py

        Returns:
            Diccionario con los metadatos del módulo o None si hay error
        """
        if not os.path.exists(manifest_path):
            return None

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parsear el archivo como AST
            tree = ast.parse(content)

            # Buscar la expresión del diccionario (el manifest es un dict)
            for node in ast.walk(tree):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
                    return ManifestParser._extract_dict(node.value)

            return None

        except Exception as e:
            print(f"Error parseando {manifest_path}: {e}")
            return None

    @staticmethod
    def _extract_dict(dict_node: ast.Dict) -> Dict[str, Any]:
        """
        Extrae un diccionario de un nodo AST Dict.

        Args:
            dict_node: Nodo AST de tipo Dict

        Returns:
            Diccionario Python con los valores extraídos
        """
        result = {}

        for key, value in zip(dict_node.keys, dict_node.values):
            if key is None:
                continue

            # Obtener el nombre de la clave
            if isinstance(key, ast.Constant):
                key_name = key.value
            elif isinstance(key, ast.Str):  # Python < 3.8
                key_name = key.s
            else:
                continue

            # Extraer el valor según su tipo
            result[key_name] = ManifestParser._extract_value(value)

        return result

    @staticmethod
    def _extract_value(node: ast.AST) -> Any:
        """
        Extrae el valor de un nodo AST.

        Args:
            node: Nodo AST

        Returns:
            Valor Python correspondiente
        """
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.List):
            return [ManifestParser._extract_value(item) for item in node.elts]
        elif isinstance(node, ast.Dict):
            return ManifestParser._extract_dict(node)
        elif isinstance(node, ast.NameConstant):  # Python < 3.8 (True, False, None)
            return node.value
        else:
            return None

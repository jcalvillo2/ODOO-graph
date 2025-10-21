"""
Parser para archivos de vistas XML de Odoo.
"""

from lxml import etree
import os
from typing import List, Optional, Dict, Any


class ViewInfo:
    """Representa información de una vista Odoo."""

    def __init__(self, view_id: str, model: str, view_type: str, file_path: str):
        self.view_id = view_id
        self.model = model
        self.view_type = view_type
        self.file_path = file_path
        self.name: Optional[str] = None
        self.inherit_id: Optional[str] = None
        self.mode: Optional[str] = None
        self.priority: Optional[int] = None

    def __repr__(self):
        return f"ViewInfo(id={self.view_id}, model={self.model}, type={self.view_type})"


class ViewParser:
    """
    Parser para extraer vistas de archivos XML de Odoo.
    """

    @staticmethod
    def parse_file(file_path: str) -> List[ViewInfo]:
        """
        Parsea un archivo XML y extrae todas las vistas Odoo.

        Args:
            file_path: Ruta al archivo .xml

        Returns:
            Lista de ViewInfo encontrados
        """
        if not os.path.exists(file_path):
            return []

        try:
            # Parsear XML
            tree = etree.parse(file_path)
            root = tree.getroot()

            views = []

            # Buscar todos los registros que sean vistas (model='ir.ui.view')
            for record in root.xpath("//record[@model='ir.ui.view']"):
                view_info = ViewParser._extract_view_info(record, file_path)
                if view_info:
                    views.append(view_info)

            return views

        except Exception as e:
            print(f"Error parseando {file_path}: {e}")
            return []

    @staticmethod
    def _extract_view_info(record_node: etree.Element, file_path: str) -> Optional[ViewInfo]:
        """
        Extrae información de un nodo <record> que representa una vista.

        Args:
            record_node: Nodo XML del record
            file_path: Ruta del archivo

        Returns:
            ViewInfo con la información de la vista
        """
        # Obtener el ID de la vista
        view_id = record_node.get('id')
        if not view_id:
            return None

        # Extraer campos del record
        model = None
        name = None
        view_type = None
        inherit_id = None
        mode = None
        priority = None

        for field in record_node.findall('field'):
            field_name = field.get('name')

            if field_name == 'model':
                model = field.text
            elif field_name == 'name':
                name = field.text
            elif field_name == 'type':
                view_type = field.text
            elif field_name == 'inherit_id':
                # inherit_id puede ser ref="module.view_id"
                inherit_ref = field.get('ref')
                if inherit_ref:
                    inherit_id = inherit_ref
                elif field.text:
                    inherit_id = field.text
            elif field_name == 'mode':
                mode = field.text
            elif field_name == 'priority':
                try:
                    priority = int(field.text) if field.text else None
                except ValueError:
                    pass
            elif field_name == 'arch' and not view_type:
                # Si no hay campo 'type', inferir del arch
                view_type = ViewParser._infer_view_type_from_arch(field)

        # Si no tenemos model, no es una vista válida
        if not model:
            return None

        # Si no tenemos tipo, intentar inferirlo del ID o arch
        if not view_type:
            view_type = ViewParser._infer_view_type_from_id(view_id)

        view_info = ViewInfo(view_id, model, view_type or 'unknown', file_path)
        view_info.name = name
        view_info.inherit_id = inherit_id
        view_info.mode = mode
        view_info.priority = priority

        return view_info

    @staticmethod
    def _infer_view_type_from_arch(arch_field: etree.Element) -> Optional[str]:
        """
        Infiere el tipo de vista desde el elemento arch.

        Args:
            arch_field: Nodo <field name="arch">

        Returns:
            Tipo de vista inferido
        """
        # Buscar el primer hijo del arch para determinar el tipo
        for child in arch_field:
            tag = child.tag
            if tag in ['tree', 'form', 'kanban', 'calendar', 'graph', 'pivot',
                      'search', 'gantt', 'activity', 'cohort', 'dashboard',
                      'map', 'qweb']:
                return tag

        return None

    @staticmethod
    def _infer_view_type_from_id(view_id: str) -> Optional[str]:
        """
        Intenta inferir el tipo de vista desde el ID.

        Args:
            view_id: ID de la vista (ej: 'view_sale_order_form')

        Returns:
            Tipo de vista inferido o None
        """
        view_id_lower = view_id.lower()

        type_keywords = {
            'form': 'form',
            'tree': 'tree',
            'list': 'tree',
            'kanban': 'kanban',
            'calendar': 'calendar',
            'graph': 'graph',
            'pivot': 'pivot',
            'search': 'search',
            'gantt': 'gantt',
            'activity': 'activity',
            'cohort': 'cohort',
            'dashboard': 'dashboard',
            'map': 'map',
            'qweb': 'qweb',
        }

        for keyword, view_type in type_keywords.items():
            if keyword in view_id_lower:
                return view_type

        return None

    @staticmethod
    def parse_directory(directory: str) -> List[ViewInfo]:
        """
        Parsea todos los archivos XML en un directorio (recursivamente).

        Args:
            directory: Directorio a parsear

        Returns:
            Lista de todas las vistas encontradas
        """
        all_views = []

        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.xml'):
                    file_path = os.path.join(root, file)
                    views = ViewParser.parse_file(file_path)
                    all_views.extend(views)

        return all_views

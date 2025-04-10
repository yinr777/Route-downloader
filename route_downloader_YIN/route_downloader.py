# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RouteDownloaderDialog
                                 A QGIS plugin
 Téléchargeur de routes OSM
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        début                : 2025-02-17
        git sha              : $Format:%H$
        copyright            : (C) 2025 par Yin Ruohan
        email                : ruohan.yin@etu-univ-grenoble-alpes.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   Ce programme est libre de droits ; vous pouvez le redistribuer ou le  *
 *   modifier selon les termes de la Licence Publique Générale GNU.        *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import (
    Qgis,
    QgsVectorLayer,
    QgsProject,
    QgsGeometry,
    QgsFeature,
    QgsPointXY,
    QgsField,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
)
from qgis.gui import QgsMapToolEmitPoint
import requests
import json
import os.path
import re

# Initialisation des ressources Qt depuis resources.py
from .resources import *
# Import de la boîte de dialogue
from .route_downloader_dialog import RouteDownloaderDialog


class RouteDownloader:
    """Implémentation du plugin QGIS."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RouteDownloader_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Téléchargeur de Routes')
        self.first_start = None
        self.canvas = self.iface.mapCanvas()
        self.point_tool = QgsMapToolEmitPoint(self.canvas)
        self.current_osm_data = {}  # Stocke les informations de limite OSM les plus récentes

    def tr(self, message):
        return QCoreApplication.translate('RouteDownloader', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        action = QAction(QIcon(icon_path), text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/route_downloader/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Téléchargeur de routes OSM'),
            callback=self.run,
            parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Téléchargeur de Routes'), action)
            self.iface.removeToolBarIcon(action)

    def get_boundary_info(self, lon, lat):
        """Récupère les informations de limite OSM (type et ID OSM)"""
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'format': 'json',
                'lat': lat,
                'lon': lon,
                'zoom': 10,
                'addressdetails': 1
            }
            headers = {'User-Agent': 'QGIS Route Downloader Plugin/1.0'}
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            result = {
                'name': data.get('display_name', ''),
                'osm_type': data.get('osm_type'),
                'osm_id': data.get('osm_id'),
                'address': data.get('address', {})
            }
            
            # Détermine automatiquement le nom administratif
            admin_levels = ['city', 'town', 'village', 'municipality', 'county', 'state']
            for level in admin_levels:
                if level in result['address']:
                    result['place_name'] = result['address'][level]
                    break
            else:
                result['place_name'] = result['name'].split(',')[0]
            
            return result
            
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                f"Échec du géocodage inverse : {str(e)}", 
                level=Qgis.Critical, 
                duration=5
            )
            return None

    def construct_overpass_query(self, osm_type, osm_id):
        """Construit une requête Overpass précise"""
        if osm_type == 'relation':
            area_id = 3600000000 + osm_id
        elif osm_type == 'way':
            area_id = 2400000000 + osm_id
        else:
            return None

        return f"""
        [out:json][timeout:25];
        area({area_id})->.searchArea;
        (
            way["highway"](area.searchArea);
        );
        (._;>;);
        out body geom;
        """

    def download_roads_geojson(self):
        """Télécharge les données routières et génère un GeoJSON"""
        if not self.current_osm_data:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                "Aucune information de limite disponible", 
                level=Qgis.Warning, 
                duration=5
            )
            return

        osm_type = self.current_osm_data.get('osm_type')
        osm_id = self.current_osm_data.get('osm_id')
        place_name = self.current_osm_data.get('place_name', 'inconnu')

        if osm_type not in ['relation', 'way'] or not osm_id:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                "Type de limite invalide", 
                level=Qgis.Warning, 
                duration=5
            )
            return

        try:
            # Construction et exécution de la requête Overpass
            query = self.construct_overpass_query(osm_type, osm_id)
            if not query:
                raise ValueError("Type de zone invalide")
                
            response = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={'data': query},
                headers={'User-Agent': 'QGIS Plugin/1.0'}
            )
            response.raise_for_status()
            data = response.json()
            
            # Génération du GeoJSON
            features = []
            nodes = {elem['id']: elem for elem in data['elements'] if elem['type'] == 'node'}
            
            for elem in data['elements']:
                if elem['type'] == 'way' and 'geometry' in elem:
                    coordinates = [[n['lon'], n['lat']] for n in elem['geometry']]
                    properties = {
                        'osm_id': elem['id'],
                        'highway': elem.get('tags', {}).get('highway', ''),
                        'name': elem.get('tags', {}).get('name', '')
                    }
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': coordinates
                        },
                        'properties': properties
                    })
            
            if not features:
                self.iface.messageBar().pushMessage(
                    "Information", 
                    "Aucune route trouvée dans la zone sélectionnée", 
                    level=Qgis.Info, 
                    duration=5
                )
                return

            geojson = {
                'type': 'FeatureCollection',
                'features': features,
                'crs': {
                    'type': 'name',
                    'properties': {'name': 'EPSG:4326'}
                }
            }

            # Sauvegarde du fichier
            sanitized_name = re.sub(r'[^a-zA-Z0-9]', '_', place_name)[:50]
            default_path = os.path.expanduser(f"~/{sanitized_name}_routes.geojson")
            path, _ = QFileDialog.getSaveFileName(
                self.dlg,
                "Enregistrer le réseau routier",
                default_path,
                "Fichiers GeoJSON (*.geojson)"
            )
            
            if not path:
                return

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, ensure_ascii=False)

            # Chargement dans QGIS
            layer = QgsVectorLayer(path, f"Routes {place_name}", "ogr")
            if not layer.isValid():
                raise ValueError("Fichier GeoJSON invalide")
                
            QgsProject.instance().addMapLayer(layer)
            self.iface.messageBar().pushMessage(
                "Succès", 
                f"{len(features)} routes sauvegardées dans {path}", 
                level=Qgis.Success, 
                duration=7
            )

        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                f"Échec du téléchargement : {str(e)}", 
                level=Qgis.Critical, 
                duration=5
            )

    def display_point(self, point, button):
        try:
            # Conversion des coordonnées en WGS84
            source_crs = self.canvas.mapSettings().destinationCrs()
            dest_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            transform = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
            wgs84_point = transform.transform(point)
            
            self.dlg.hide()
            
            # Récupération des informations de limite
            boundary_info = self.get_boundary_info(wgs84_point.x(), wgs84_point.y())
            if not boundary_info:
                return
                
            self.current_osm_data = boundary_info
            
            # Mise à jour de l'interface
            self.dlg.lineEdit_cor.setText(f"{wgs84_point.x():.6f}, {wgs84_point.y():.6f}")
            self.dlg.lineEdit_lieu.setText(boundary_info['place_name'])
            
            self.dlg.show()
            
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                f"Erreur de traitement du point : {str(e)}", 
                level=Qgis.Critical, 
                duration=5
            )
            self.dlg.show()

    def start_download(self):
        """Déclenche le processus de téléchargement"""
        if not self.current_osm_data:
            self.iface.messageBar().pushMessage(
                "Erreur", 
                "Veuillez d'abord sélectionner un lieu", 
                level=Qgis.Warning, 
                duration=5
            )
            return
            
        self.download_roads_geojson()

    def run(self):
        if self.first_start:
            self.first_start = False
            self.dlg = RouteDownloaderDialog()
            self.point_tool.canvasClicked.connect(self.display_point)
            self.dlg.pushButton_telechargement.clicked.connect(self.start_download)
        
        self.canvas.setMapTool(self.point_tool)
        self.dlg.show()

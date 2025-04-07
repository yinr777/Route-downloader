Plugin Builder Results

Your plugin RouteDownloader was created in:
    /home/yinr/Documents/pyqgis/route_downloader

Your QGIS plugin directory is located at:
    /home/yinr/.local/share/QGIS/QGIS3/profiles/default/python/plugins

 1. Aperçu

Le plugin RouteDownloader est un outil basé sur QGIS destiné à télécharger des données routières pour une zone spécifiée à partir d'OpenStreetMap (OSM). Le plugin utilise le service de géocodage inverse de Nominatim pour déterminer les limites administratives de la zone sélectionnée par l'utilisateur et construit une requête via l'API Overpass pour récupérer les données routières. Les données sont ensuite converties en un fichier GeoJSON et chargées en tant que couche vectorielle dans QGIS.

2. Exigences et dépendances

 Bibliothèques Python

- requests : pour effectuer des requêtes réseau avec les API Nominatim et Overpass.  
- json, os.path, re : pour le traitement des données et la gestion des fichiers.

3. Processus d'utilisation du plugin

 Démarrage du plugin

1. Chargez le plugin dans QGIS.
2. Lancez RouteDownloader via la barre d'outils ou le menu du plugin.

 Sélection de la zone

- Après le démarrage, l'outil de carte passe en mode de sélection par clic.
- L'utilisateur clique sur un emplacement de la carte. Le plugin capture les coordonnées du clic et les convertit en coordonnées WGS84.

 Obtention des informations de la zone

- Le plugin utilise le géocodage inverse (API Nominatim) pour obtenir les informations administratives correspondant au point cliqué.
- Les coordonnées et le nom de la zone sont affichés dans la boîte de dialogue du plugin.

 Exécution du téléchargement

- Après confirmation par l'utilisateur, le plugin construit la requête Overpass pour télécharger toutes les données routières de la zone sélectionnée.
- Les données sont converties en un fichier GeoJSON. Une boîte de dialogue s'ouvre pour permettre à l'utilisateur de choisir l'emplacement de sauvegarde.

 Chargement de la couche de données

- Une fois le fichier GeoJSON sauvegardé avec succès, le plugin charge automatiquement cette couche dans QGIS.
- Un message de succès indiquant le nombre de routes téléchargées est affiché dans la barre de messages.


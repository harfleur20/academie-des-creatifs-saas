// Ajouté à la configuration générée par l'image web de docker-jitsi-meet.
// Les salles s'ouvrent dans la page du SaaS : pas d'accueil Jitsi ni de liens vers l'application mobile.
// La page du SaaS a son propre accueil (micro, caméra) : celui de Jitsi est désactivé.
config.defaultLanguage = 'fr';
config.prejoinConfig = { enabled: false };
config.disableDeepLinking = true;
config.enableWelcomePage = false;
config.enableClosePage = false;
config.disableInviteFunctions = true;
config.doNotStoreRoom = true;
// Les classes ont souvent plus de 2 participants : pas de pair-à-pair, tout passe par les relais vidéo.
config.p2p = { enabled: false };
// Économise la bande passante des étudiants : la vidéo principale en 720p au plus.
config.resolution = 720;
config.constraints = { video: { height: { ideal: 720, max: 720, min: 180 } } };

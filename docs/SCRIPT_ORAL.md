# Script de soutenance — SENTINEL-X, Groupe 1

Soutenance de campus, 10 minutes chrono imposées par le sujet. Six intervenants, une partie chacun.
Remplacez les crochets `[Nom]` par les prénoms. Les indications entre *italiques* sont des gestes, pas du texte à dire.

## Qui parle quand

| Temps | Séquence | Intervenant | Rôle |
|-------|----------|-------------|------|
| 0:00–1:00 | Introduction | **[Nom 1]** | Ouvre, plante le décor AetherCorp, annonce la variante B |
| 1:00–2:00 | Projection du teaser | *(aucun, la vidéo parle)* | [Nom 1] lance la vidéo puis se range |
| 2:00–3:00 | Démo live — le boîtier | **[Nom 2]** | Montre le matériel, déclenche une alerte réelle |
| 3:00–4:00 | Démo live — le dashboard | **[Nom 3]** | Télémétrie temps réel, envoie une commande |
| 4:00–5:00 | Démo live — l'IA | **[Nom 4]** | Vision : intrus détecté, personne autorisée reconnue |
| 5:00–7:00 | Pitch — architecture | **[Nom 5]** | La chaîne de données et les choix techniques |
| 7:00–9:00 | Pitch — sécurité | **[Nom 6]** | Les quatre couches, le pentest, la conclusion |
| 9:00–10:00 | Questions | **tous** | Chacun répond sur sa partie |

Règle d'or : on se passe la parole par une phrase de relais, jamais par un blanc. On ne lit pas ses notes, on connaît ses trois idées.

---

## 0:00 – 1:00 · Introduction — [Nom 1]

*Debout, face au jury, les six alignés derrière.*

« Bonjour. Nous sommes le consortium d'ingénieurs du Groupe 1, et nous répondons à une commande d'AetherCorp.

Les centrales d'AetherCorp sont des sites critiques, souvent isolés, où une fuite de gaz, une surchauffe ou une intrusion doivent être détectées en quelques secondes, même sans connexion au cloud.

Notre réponse, c'est Sentinel-X : un module de sécurité à la bordure. Toute l'intelligence est embarquée sur place, et un serveur local traite le reste. Nous avons choisi la variante B du sujet : pas de Raspberry Pi, c'est notre poste serveur qui joue le PC local, avec les conteneurs, l'API et l'IA.

En une phrase : Sentinel-X surveille, décide et alerte sur site, sans dépendre d'internet. Place au teaser. »

*[Nom 1] lance la vidéo et se range dans la ligne.*

## 1:00 – 2:00 · Teaser « Sentinel Drop »

*La vidéo verticale de 60 secondes est projetée. Personne ne parle. On regarde le jury, pas l'écran.*

---

## 2:00 – 3:00 · Démo live, le boîtier — [Nom 2]

*Prend le boîtier en main, le montre au jury.*

« Voici Sentinel-X en vrai. Le boîtier est imprimé en 3D au Fablab et la façade est gravée au laser, avec le logo AetherCorp et le numéro de série.

À l'intérieur, un microcontrôleur ESP8266 et ses capteurs : température et humidité, gaz et fumée, et un détecteur de présence. L'écran OLED fait défiler l'état en direct : identité, réseau, mesures.

Je déclenche une alerte réelle, maintenant. *[approche un briquet non allumé du capteur de gaz, ou passe la main devant le détecteur]* Regardez l'écran : il bascule en alerte, la LED passe au rouge, et la sirène se déclenche.

Tout ça est décidé par le boîtier lui-même, sans serveur. Et cette même alerte part vers notre poste serveur. [Nom 3] va vous montrer ce qu'il en fait. »

## 3:00 – 4:00 · Démo live, le dashboard — [Nom 3]

*Devant l'écran du dashboard, déjà ouvert.*

« Côté serveur, voici le centre de commandement. L'alerte que [Nom 2] vient de déclencher est déjà là : vous la voyez apparaître en temps réel.

Le boîtier publie ses mesures toutes les cinq secondes. Le serveur les enregistre et les pousse instantanément à l'écran par WebSocket : la courbe de température, le niveau de gaz, la présence. Aucune page à recharger.

Et ça marche dans les deux sens. Je peux reprendre la main sur le boîtier. *[clique sur le bouton Alarme]* J'envoie une commande, elle traverse le serveur, et la sirène du boîtier se déclenche à distance. C'est le superviseur qui garde le contrôle.

Jusqu'ici, ce sont des seuils simples. La vraie intelligence, c'est [Nom 4] qui va vous la montrer. »

## 4:00 – 5:00 · Démo live, l'IA — [Nom 4]

*Devant la fenêtre de la caméra.*

« Sentinel-X ne se contente pas de capteurs. Une webcam surveille la zone, et une IA de vision tourne sur le serveur.

*[se place devant la caméra, ou fait passer un complice]* Quand une personne entre dans le champ, l'IA la détecte et le signale comme intrusion : le boîtier affiche « alerte caméra » et déclenche la sirène.

Mais tout le monde n'est pas un intrus. *[se montre au cadre]* Mon visage a été enregistré comme personne autorisée. L'IA me reconnaît et ne déclenche aucune alerte. Un visage inconnu, lui, lève l'alarme immédiatement.

En plus de ça, un deuxième modèle analyse l'historique des mesures et repère les dérives lentes et anormales que de simples seuils rateraient. Voilà pour la démonstration. [Nom 5] va expliquer comment tout ça tient ensemble. »

---

## 5:00 – 7:00 · Pitch, l'architecture — [Nom 5]

*Support de présentation : schéma d'architecture.*

« Ce que vous venez de voir repose sur une chaîne simple et robuste.

Le boîtier parle au serveur en MQTT, un protocole léger fait pour les objets connectés. Sur le serveur, un broker Mosquitto reçoit les messages. Une API en Python, FastAPI, les valide, les enregistre dans une base PostgreSQL, et les diffuse au dashboard React en temps réel.

Nous avons fait des choix assumés. MQTT plutôt que HTTP sur le boîtier, parce qu'il gère tout seul les reconnexions et prévient le serveur si le boîtier tombe. FastAPI parce qu'il est asynchrone, parfait pour le temps réel, et qu'il documente l'API tout seul. Toute la pile serveur tient dans des conteneurs Docker : on la démarre en une commande, elle est identique sur n'importe quelle machine.

Et surtout, tout fonctionne en local. Coupez internet, Sentinel-X continue de mesurer, de décider et d'alerter. C'est le cœur de la variante B. La robustesse de ce lien, c'est [Nom 6] qui va vous en parler, côté sécurité. »

## 7:00 – 9:00 · Pitch, la sécurité — [Nom 6]

*Support : la diapositive « Sécurité de la liaison ».*

« AetherCorp est une cible. Notre liaison est protégée par quatre couches, pas un seul verrou.

D'abord le chiffrement. Le boîtier parle au serveur en TLS 1.3. Tout le trafic est illisible pour qui écoute le Wi-Fi, même sur un réseau partagé avec d'autres équipes. Le boîtier vérifie l'empreinte du certificat : impossible de se faire passer pour notre serveur.

Ensuite l'authentification. Le broker refuse toute connexion anonyme, et chaque commande envoyée à l'API exige une clé secrète. Une tentative sans identifiants est rejetée, nous pouvons vous le montrer en direct.

Troisième couche, le cloisonnement : la base de données n'est ouverte sur aucun port, et la clé secrète ne quitte jamais le serveur.

Quatrième couche, la détection : pendant le pentest, un moniteur affiche en direct toute connexion suspecte et tout échec d'authentification.

Nous assumons nos limites, et elles sont dans notre plan de durcissement. Sentinel-X, c'est la sécurité à la bordure : embarquée, chiffrée, et qui ne lâche jamais le terrain. Merci. »

*Les six se réalignent face au jury pour les questions.*

---

## 9:00 – 10:00 · Questions

Qui répond à quoi, pour ne pas se couper la parole :

- **Matériel, capteurs, seuils, alertes** → [Nom 2]
- **Dashboard, API, base de données, temps réel** → [Nom 3] et [Nom 5]
- **IA vision et modèle prédictif** → [Nom 4]
- **Sécurité, TLS, pentest, durcissement** → [Nom 6]
- **Choix de la variante B, organisation, Fablab** → [Nom 1]

Questions probables et réponse courte prête :
- *« Que se passe-t-il si le serveur tombe ? »* → Le boîtier continue de mesurer et d'alerter localement ; à son retour, le serveur le remarque et rattrape l'état.
- *« Pourquoi pas de Raspberry Pi ? »* → Variante B du sujet : notre poste joue le serveur local, moins de matériel à maintenir pour la démo.
- *« Votre chiffrement résiste à une interception ? »* → Oui, TLS 1.3 ; une capture réseau ne montre que des données chiffrées, aucun JSON lisible.
- *« L'IA tourne où ? »* → Sur le serveur local, en edge, pas dans le cloud.

## Conseils de passage

- Répétez au moins deux fois en entier, chrono en main. Le respect du temps est noté.
- Parlez au jury, pas à l'écran ni à vos notes.
- Phrases courtes, débit calme. Mieux vaut dire moins et clair que tout et vite.
- Préparez une roue de secours pour la démo : si un capteur ne répond pas, enchaînez sur le dashboard et dites-le sans paniquer. Un incident bien géré en direct rassure plus qu'une démo parfaite récitée.

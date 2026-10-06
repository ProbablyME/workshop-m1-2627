# Câblage du boîtier SENTINEL-X (Groupe 1)

Carte : **NodeMCU Lolin v3 (ESP8266 ESP-12E)**, montée sur le pack myDiL avec 2 breadboards
170 points. **Ne pas désassembler le pack.** Toutes les entrées/sorties de l'ESP sont en **3,3 V**.

## 0. Montage minimal (celui qu'on fait)

Tout sur l'USB, sans transistor ni pont diviseur ni bloc 7,5 V. Suffisant pour la démo.

| Composant | Branchement                                                     |
|-----------|-----------------------------------------------------------------|
| OLED      | SCL → D1, SDA → D2, VCC → 3V, GND → G                           |
| DHT22     | DATA → D5, VCC → 3V, GND → G                                    |
| PIR       | OUT → D6, VCC → VU (5 V USB), GND → G                           |
| MQ-2      | AO → A0, **VCC → 3V** (pas 5 V : sans diviseur, A0 reste sous 3,3 V), GND → G |
| LED       | rouge → 220 Ω → D0, verte → 220 Ω → D8, cathode commune → G     |
| Buzzer passif 3 broches | S (signal) → D7, VCC → VU (5 V, plus fort) ou 3V, GND → G. Broche du milieu sans nom : laisser libre. Le firmware joue une mélodie (thème Mario) par PWM |

Courses : 13 câbles mâle/femelle, 4 mâle/mâle, 2 résistances 220 Ω. C'est tout.
Le MQ-2 en 3,3 V est moins sensible mais réagit à un briquet non allumé ou à un coton d'alcool.
Mettre `MQ2_DIVIDER_RATIO 1.0f` et `MQ2_VCC 3.3f` dans `firmware/include/config.h`.
Les sections suivantes décrivent la version complète, optionnelle.

## 1. Brochage retenu

| Composant            | Broche composant | Broche NodeMCU | GPIO   | Remarque                                            |
|----------------------|------------------|----------------|--------|-----------------------------------------------------|
| OLED 0.96" I2C       | SCL              | **D1**         | GPIO5  | bus I2C                                             |
| OLED 0.96" I2C       | SDA              | **D2**         | GPIO4  | bus I2C                                             |
| OLED 0.96" I2C       | VCC / GND        | 3V / G         |        | adresse 0x3C                                        |
| DHT22 (module 3 pins)| DATA             | **D5**         | GPIO14 | le module intègre la résistance de pull-up          |
| DHT22                | VCC / GND        | 3V / G         |        | fonctionne en 3,3 V                                 |
| PIR HC-SR501         | OUT              | **D6**         | GPIO12 | sortie 3,3 V, sans danger pour l'ESP                |
| PIR HC-SR501         | VCC / GND        | **5V** / G     |        | régulateur embarqué, alimenter en 5 V               |
| MQ-2                 | AO               | **A0**         | ADC    | **via pont diviseur** 10 kΩ / 20 kΩ (voir §3)       |
| MQ-2                 | DO               | non câblé      |        | sortie 5 V, interdite sur l'ESP                     |
| MQ-2                 | VCC / GND        | **5V** / G     |        | résistance chauffante ~150 mA                       |
| Buzzer actif 3 V     | +                | **D7**         | GPIO13 | via transistor NPN (§3), ou direct pour tester      |
| LED bicolore         | anode ROUGE      | **D0**         | GPIO16 | résistance 220 Ω en série                           |
| LED bicolore         | anode VERTE      | **D8**         | GPIO15 | résistance 220 Ω en série                           |
| LED bicolore         | cathode commune  | G              |        |                                                     |

Pourquoi ces broches : **D3 (GPIO0), D4 (GPIO2)** doivent être à l'état haut au démarrage et
**D8 (GPIO15)** à l'état bas, sinon l'ESP part en mode flash ou ne boote pas. Une LED vers la
masse sur D8 respecte cette règle ; une LED sur D3 ou D4 l'enfreint. D0 n'a pas de PWM ni
d'interruption, ce qui est sans importance pour une LED.

Le **5V** est la broche **VU** (« VOUT USB ») de la Lolin v3 en phase développement, ou le
rail 5 V du convertisseur DC-DC en phase production (§4).

## 2. Liste de courses au myDiL

### Câbles Dupont

| Type               | Quantité | Usage                                                         |
|--------------------|----------|---------------------------------------------------------------|
| **Mâle / Femelle** | **15**   | modules à connecteurs mâles vers breadboard : OLED 4, DHT22 3, PIR 3, MQ-2 3, + 2 de réserve |
| **Mâle / Mâle**    | **10**   | ponts sur breadboard : rails 3,3 V / 5 V / masse, diviseur, transistor, LED |
| USB-A vers micro-USB 1 m | 1  | fourni, flash + alimentation en développement                 |

Prendre des câbles **courts (10 cm)** pour l'intérieur du boîtier, sauf 3 de 20 cm pour le PIR
qui sera sur la face avant.

### Composants passifs et actifs

| Composant                    | Quantité | Usage                                           |
|------------------------------|----------|-------------------------------------------------|
| Résistance 220 Ω (ou 330 Ω)  | 2        | protection LED rouge / verte                    |
| Résistance 10 kΩ             | 1        | diviseur MQ-2 (haut)                            |
| Résistance 20 kΩ (ou 2×10 kΩ en série) | 1 | diviseur MQ-2 (bas)                            |
| Transistor NPN (2N2222, S8050, BC547) | 1 | commande buzzer                               |
| Résistance 1 kΩ              | 1        | base du transistor                              |
| Bloc 220 V → 7,5 V + 2 Wago  | 1        | alimentation phase production                   |
| Convertisseur DC-DC 7,5 V → 5 V | 1     | rail 5 V pour PIR + MQ-2 en production          |

Si le myDiL n'a pas de transistor, le buzzer actif 3 V peut se brancher directement D7 → buzzer+
et buzzer− → G pour les tests. Un GPIO ESP8266 délivre 12 mA : si le buzzer réclame plus, il
sonnera faiblement et l'ESP peut redémarrer. Le transistor est la solution propre.

## 3. Schémas des sous-ensembles

### Diviseur de tension MQ-2 → A0

La sortie AO du MQ-2 monte jusqu'à 5 V. L'entrée A0 de la NodeMCU accepte 0 à 3,3 V.

```
MQ-2 AO ───[ 10 kΩ ]───┬─── A0 (NodeMCU)
                       │
                    [ 20 kΩ ]
                       │
                      GND
```

V(A0) = V(AO) × 20 / 30, donc 5 V → 3,33 V. Le firmware multiplie par 1,5 (`MQ2_DIVIDER_RATIO`).

Alternative dégradée : alimenter le MQ-2 en 3,3 V sans diviseur. La sensibilité chute fortement,
à n'utiliser qu'en dépannage.

### Commande du buzzer par transistor NPN

```
D7 ───[ 1 kΩ ]─── Base
                  Collecteur ─── Buzzer (−)
                                 Buzzer (+) ─── 3V (ou 5V si buzzer 5 V)
                  Émetteur ───── GND
```

Le buzzer est actif (mono-ton) : un niveau haut sur D7 le fait sonner, pas besoin de PWM.

### LED bicolore à cathode commune

```
D0 ───[ 220 Ω ]─── anode ROUGE ─┐
D8 ───[ 220 Ω ]─── anode VERTE ─┤ LED
                   cathode ─────┴─── GND
```

Identifier les pattes : la plus longue est en général la cathode commune, à vérifier au multimètre
ou en testant avec 3V + résistance.

## 4. Alimentation : deux modes, jamais les deux en même temps

| Mode                 | ESP8266                  | Rail 5 V (PIR, MQ-2)          | Rail 3,3 V (OLED, DHT22) |
|----------------------|--------------------------|-------------------------------|--------------------------|
| **Développement**    | câble USB depuis le PC   | broche **VU** de la NodeMCU   | broche **3V**            |
| **Production (démo)**| bloc 7,5 V → DC-DC 5 V → **VIN** | sortie du DC-DC 5 V    | broche **3V**            |

Règle absolue du myDiL : **ne jamais brancher le bloc 7,5 V sur VIN pendant que le câble USB
est connecté.** Pour flasher en phase production, débrancher le bloc, brancher l'USB, flasher,
débrancher l'USB, rebrancher le bloc.

Pourquoi passer par le DC-DC avant VIN plutôt que 7,5 V direct sur VIN : le régulateur AMS1117
de la NodeMCU chauffe nettement sous 7,5 V, et le rail 5 V est de toute façon nécessaire pour le
PIR et le MQ-2. Une seule source 5 V alimente tout, c'est plus simple à câbler proprement dans le
boîtier. Le schéma du myDiL (7,5 V sur VIN + DC-DC séparé) fonctionne aussi.

Budget courant en 5 V : ESP ~80 mA (pics 300 mA Wi-Fi) + MQ-2 150 mA + PIR 65 mA + OLED 20 mA
+ buzzer 30 mA ≈ 350 mA, pics 600 mA. Le bloc 1 A et un port USB 500 mA conviennent (le MQ-2
peut être laissé débranché pendant le flash si le port USB est faible).

## 5. Ordre de montage conseillé (mardi matin)

1. ESP seul en USB, flasher le firmware, vérifier l'OLED (adresse 0x3C) : le plus simple à valider.
2. DHT22 sur D5 : vérifier température et humidité sur le moniteur série.
3. PIR sur D6 : régler les deux potentiomètres (sensibilité à mi-course, délai au minimum), cavalier en mode « H » (répétable).
4. LED + résistances, puis buzzer + transistor : tester avec `POST /commands`.
5. MQ-2 en dernier avec son diviseur, laisser chauffer 2 à 3 minutes avant de lire des valeurs stables.
6. Vérifier dans le dashboard que la télémétrie arrive, puis passer en MQTTS.

## 6. Pièges connus

- Le MQ-2 chauffe (normal) et consomme : le brancher en dernier, sur le 5 V, jamais sur le 3V de l'ESP pour l'OLED partagé.
- Le PIR met 30 à 60 s à se stabiliser après mise sous tension et déclenche à vide pendant ce temps.
- Le DHT22 ne se lit pas plus d'une fois toutes les 2 s.
- Lire A0 trop souvent perturbe le Wi-Fi : le firmware le lit toutes les 2 s, ne pas descendre en dessous.
- Un reset en boucle avec le message `rst cause:4` ou `wdt reset` signale une alimentation faible ou un GPIO de boot mal tiré (D3/D4/D8).
- **Port série qui disparaît sur macOS** (« Resource busy », « Device not configured ») : le pilote CH340 natif de macOS 14/15 détache la carte quand un programme force les lignes DTR/RTS à l'ouverture du port. Ce n'est pas un problème d'alimentation : un ESP seul tient très bien sur un hub USB. Utiliser `make monitor` (`pio device monitor`), qui ouvre le port correctement, et ne pas écrire de script série maison qui met DTR/RTS à 0 avant l'ouverture. Si le problème persiste, installer le pilote WCH CH34xVCPDriver.

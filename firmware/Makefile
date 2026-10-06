# Raccourcis PlatformIO sans IDE. Utilisation :
#   make build      compile
#   make upload     compile + flashe (ESP en USB, bloc 7,5 V débranché)
#   make monitor    moniteur série 115200 bauds (Ctrl+C pour quitter)
#   make flash      upload + monitor enchaînés
#   make ports      liste les ports série détectés
#   make bench-upload  flashe la variante sans Wi-Fi (banc d'essai, hub USB faible)
#   make clean      supprime les binaires
# Variable optionnelle : make upload PORT=/dev/cu.usbserial-1420  (ou COM5 sous Windows)

PIO := $(shell command -v pio 2>/dev/null || ls $(HOME)/.platformio/penv/bin/pio 2>/dev/null || echo pio)
PORTFLAG := $(if $(PORT),--upload-port $(PORT),)
MONFLAG  := $(if $(PORT),--port $(PORT),)

.PHONY: build upload monitor flash ports clean secrets bench-upload

build: secrets
	$(PIO) run

upload: secrets
	$(PIO) run -t upload $(PORTFLAG)

monitor:
	$(PIO) device monitor -b 115200 $(MONFLAG)

flash: upload monitor

ports:
	$(PIO) device list

bench-upload: secrets
	$(PIO) run -e bench -t upload $(PORTFLAG)

clean:
	$(PIO) run -t clean

secrets:
	@test -f include/secrets.h || { cp include/secrets.h.example include/secrets.h; echo ">>> include/secrets.h créé depuis l'exemple : remplir Wi-Fi, MQTT et empreinte TLS"; }

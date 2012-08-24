default: packages

packages: build/betterponymotes.xpi build/betterponymotes.crx build/betterponymotes.oex

emote-classes.css nsfw-emote-classes.css emote-map.js: bin/bpgen.py emotes/*.yaml
	bin/bpgen.py emotes/*.yaml

build/betterponymotes.xpi: emote-classes.css nsfw-emote-classes.css emote-map.js firefox/data/* firefox/package.json firefox/lib/main.js
	cfx xpi --update-url=http://rainbow.mlas1.us/betterponymotes.update.rdf --pkgdir=firefox
	mv betterponymotes.xpi build

unpack-xpi:
	mkdir xpi
	unzip build/betterponymotes.xpi -d xpi

pack-xpi:
	cd xpi && zip -r ../build/betterponymotes.xpi * && cd ..
	rm -r xpi
	cp build/betterponymotes.xpi build/betterponymotes_`bin/version.py get`.xpi
	uhura -k betterponymotes.pem build/betterponymotes_`bin/version.py get`.xpi http://rainbow.mlas1.us/betterponymotes_`bin/version.py get`.xpi > files/betterponymotes.update.rdf

build/betterponymotes.crx: emote-classes.css nsfw-emote-classes.css emote-map.js chrome/*
	google-chrome --pack-extension=chrome --pack-extension-key=betterponymotes.pem
	mv chrome.crx build/betterponymotes.crx
	cp build/betterponymotes.crx build/betterponymotes_`bin/version.py get`.crx

build/betterponymotes.oex: emote-classes.css nsfw-emote-classes.css emote-map.js opera/includes/betterponymotes.js opera/includes/* opera/*
	cd opera && zip -r ../build/betterponymotes.oex * && cd ..
	cp build/betterponymotes.oex build/betterponymotes_`bin/version.py get`.oex

opera/includes/betterponymotes.js: bin/make_opera_script.py opera/includes/betterponymotes.js.in emote-map.js
	bin/make_opera_script.py

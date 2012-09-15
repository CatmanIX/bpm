/*******************************************************************************
**
** Copyright (C) 2012 Typhos
**
** This Source Code Form is subject to the terms of the Mozilla Public
** License, v. 2.0. If a copy of the MPL was not distributed with this
** file, You can obtain one at http://mozilla.org/MPL/2.0/.
**
*******************************************************************************/

"use strict";

var match_pattern = require("match-pattern");
var page_mod = require("page-mod");
var self = require("self");
var simple_prefs = require("simple-prefs");
var simple_storage = require("simple-storage");
var tabs = require("tabs");

var pref_setup = require("pref-setup");
var sr_data = require("sr-data");

var storage = simple_storage.storage;

if(!storage.prefs) {
    storage.prefs = {};

    if(simple_prefs.prefs.enableNSFW !== undefined) {
        // Copy old prefs
        storage.prefs.enableNSFW = simple_prefs.prefs.enableNSFW;
        storage.prefs.enableExtraCSS = simple_prefs.prefs.enableExtraCSS;
    }
}

pref_setup.setup_prefs(storage.prefs);

function on_cs_attach(worker) {
    worker.port.on("get_prefs", function() {
        worker.port.emit("prefs", storage.prefs);
    });
    worker.port.on("set_prefs", function(prefs) {
        storage.prefs = prefs;
        prefs_updated();
    });
}

// Setup communication with prefs page
var prefs_mod = page_mod.PageMod({
    include: [self.data.url("options.html")],
    contentScriptWhen: "start",
    contentScriptFile: [
        self.data.url("emote-map.js"),
        self.data.url("sr-data.js"),
        self.data.url("options.js")
        ],
    onAttach: on_cs_attach
});

// Enable the button that opens the page
simple_prefs.on("openPrefs", function() {
    tabs.open(self.data.url("options.html"));
});

// Main script. As an optimization, we just replace this mod (in order to change
// the list of matching URLs) whenever the global conversion option changes, so
// that the script doesn't needlessly run on all pages if BGM is disabled.
//
// This has a nasty side effect- the workers get "disconnected" and don't seem
// to be able to save settings. Consequently, changing the BGM option will mean
// all currently-open pages won't save the emote search window. I think.
var main_mod = null;

// Previous global emotes setting. Compare with ===/!== so the null triggers the
// initial run properly in prefs_updated().
var bgm_enabled = null;

// Monitor prefs for CSS-related changes
function prefs_updated() {
    var bgm_changed = storage.prefs.enableGlobalEmotes !== bgm_enabled;

    if(bgm_changed) {
        if(main_mod !== null) {
            main_mod.destroy();
        }

        main_mod = page_mod.PageMod({
            include: [storage.prefs.enableGlobalEmotes ? "*" : "*.reddit.com"],
            contentScriptWhen: "start",
            contentScriptFile: [
                self.data.url("emote-map.js"),
                self.data.url("sr-data.js"),
                self.data.url("betterponymotes.js")
                ],
            onAttach: on_cs_attach
            });
    }

    bgm_enabled = storage.prefs.enableGlobalEmotes;
}

prefs_updated(); // Initial run

#!/usr/bin/env python3
# -*- coding: utf8 -*-
################################################################################
##
## Copyright (C) 2012 Typhos
##
## This Source Code Form is subject to the terms of the Mozilla Public
## License, v. 2.0. If a copy of the MPL was not distributed with this
## file, You can obtain one at http://mozilla.org/MPL/2.0/.
##
################################################################################

import argparse
import time

import bplib

### Emote loading

class EmoteFile:
    def __init__(self, meta, emotes):
        self.meta = meta
        self.emotes = emotes

        self.name = meta["Name"]

    @classmethod
    def from_data(cls, data):
        meta = data.pop("Meta")
        emote_data = data.pop("Emotes")
        emotes = {}

        def update(d):
            for name_pair in d:
                if name_pair in emotes:
                    print("ERROR: Duplicate emote", name_pair)
            emotes.update(d)

        update(convert_spritesheets(emote_data.pop("Spritesheets", {})))
        update(convert_customs(emote_data.pop("Custom", {})))

        for key in emote_data:
            print("ERROR: Unknown emote section in file")
        for key in data:
            print("ERROR: Unknown key in file")

        return cls(meta, emotes)

    def __repr__(self):
        return "EmoteFile(%r, %r)" % (self.meta, self.emotes)

def convert_spritesheets(raw_spritesheets):
    # Loads all spritesheets
    emotes = {}
    for (image_url, emote_list) in raw_spritesheets.items():
        for data in emote_list:
            emote = bplib.Emote.from_data(image_url, data)
            name_pair = (emote.name, emote.suffix)
            if name_pair in emotes:
                print("ERROR: Duplicate emotes", name_pair)
            emotes[name_pair] = emote
    return emotes

def convert_customs(customs):
    # Loads all custom emotes
    emotes = {}
    for data in customs:
        emote = bplib.RawEmote.from_data(data)
        name_pair = (emote.name, emote.suffix)
        if name_pair in emotes:
            print("ERROR: Duplicate emotes", name_pair)
        emotes[name_pair] = emote
    return emotes

### Directive application

def resolve_emotes(files, data):
    file_ignores = data.pop("File Ignores")
    sorting_rules = data.pop("Sorting")
    _conflict_rules = data.pop("Conflicts")
    directive_map = data.pop("Directives")

    conflict_rules = {tuple(d["Name"]): d["Favor"] for d in _conflict_rules}

    def overrides(base, new, name_pair):
        for rule in sorting_rules:
            if rule == [base, "*"]: # Old subreddit wins all
                return False
            elif rule == [new, "*"]: # New subreddit wins all
                return True
            elif rule == [base, new]: # Old subreddit wins vs. new
                return False
            elif rule == [new, base]: # New subreddit wins vs. old
                return True

        if name_pair in conflict_rules:
            # Does either subreddit explicitly win for this emote?
            favor = conflict_rules[name_pair]
            if favor == base:
                return False
            elif favor == new:
                return True

        # No solution
        return None

    for filename in file_ignores:
        if filename in files:
            del files[filename]

    # Converts a list of files into one big emote map
    emotes = {}
    sources = {}

    conflicts = {}

    # Sort all emotes by prioritization
    for file in files.values():
        for (name_pair, emote) in file.emotes.items():
            if name_pair in emotes:
                result = overrides(sources[name_pair], file.name, name_pair)
                if result:
                    # Get rid of the old one so it can't hurt anyone anymore
                    del files[sources[name_pair]].emotes[name_pair]
                    if name_pair in conflicts:
                        del conflicts[name_pair]
                    # Replace emote
                    emotes[name_pair] = emote
                    sources[name_pair] = file.name
                elif result is None:
                    # ?!? first file wins I guess
                    conflicts[name_pair] = (file.name, sources[name_pair])
            else:
                emotes[name_pair] = emote
                sources[name_pair] = file.name

    for (name_pair, (old, new)) in conflicts.items():
        print("ERROR: CONFLICT between %s and %s over %s" % (old, new, name_pair))

    # Apply custom directives
    for (filename, directives) in directive_map.items():
        for d in directives:
            if isinstance(d, str):
                op = d
                args = ()
            else:
                op = d[0]
                args = d[1:]
            Directives[op](emotes, files[filename], *args)

    return emotes

def d_add_css(emotes, file, emote, css):
    emotes[parse_emote(emote)].css.update(css)

def d_mark_nsfw(emotes, file, *es):
    for e in es:
        file.emotes[parse_emote(e)].nsfw = True

def d_set_selector(emotes, file, emote, to):
    assert file.emotes[parse_emote(emote)].selector is None
    file.emotes[parse_emote(emote)].selector = to

def d_disable_css(emotes, file, emote):
    file.emotes[parse_emote(emote)].nocss = True

def d_remove_emote(emotes, file, emote):
    del emotes[parse_emote(emote)]
    del file.emotes[parse_emote(emote)]

def parse_emote(s):
    if isinstance(s, list):
        return tuple(s)
    else:
        return (s, None)

Directives = {
    "AddCSS": d_add_css,
    "MarkNSFW": d_mark_nsfw,
    "SetSelector": d_set_selector,
    "DisableCSS": d_disable_css,
    "Remove": d_remove_emote,
    }

### Generation

def build_css(emotes):
    css_rules, nsfw_css_rules = {}, {}

    for emote in emotes.values():
        if emote.nocss:
            continue

        target = (nsfw_css_rules if emote.nsfw else css_rules)
        selector, properties = emote.to_css()
        if selector in target:
            print("ERROR: Selector %r used twice!" % (selector))
        target[selector] = properties

    return css_rules, nsfw_css_rules

def build_js(emotes):
    emote_map = {}

    for emote in emotes.values():
        if emote.suffix is not None:
            # Assume we should ignore- I can't think of when this isn't true
            continue

        assert emote.name not in emote_map
        emote_map[emote.name] = int(emote.nsfw) + 1

    return emote_map

def condense_css(rules):
    # Locate all known CSS properties, and sort selectors by their value
    properties = {}
    for (selector, props) in rules.items():
        for (prop_name, prop_value) in props.items():
            properties.setdefault(prop_name, {}).setdefault(prop_value, [])
            properties[prop_name][prop_value].append(selector)

    def common_selectors(props):
        i = iter(props.items())

        try:
            (k, v) = next(i)
        except StopIteration:
            return set()
        common = set(properties.get(k, {}).get(v, []))

        for (k, v) in i:
            these = set(properties.get(k, {}).get(v, []))
            common = common.intersection(these)

        return common

    def condense(common_props):
        # Assume they're common
        selectors = common_selectors(common_props)
        if len(selectors) <= 1:
            return

        # TODO: frozenset? probably doesn't matter if we sort
        sel_string = ",".join(sorted(selectors))

        props_chars = sum((len(key) + len(val) + 1) for (key, val) in common_props.items())
        chars_added = len(sel_string) + props_chars

        chars_removed = 0
        for sel in selectors:
            chars_removed += props_chars
            if len(rules[sel]) <= len(common_props):
                chars_removed += len(sel) + 2

        if chars_added > chars_removed:
            return

        existing_props = rules.setdefault(sel_string, {})
        for (prop_name, value) in common_props.items():
            # Make sure we're not screwing anything up
            if prop_name in existing_props:
                print("WARNING: condensing same property twice", prop_name, "=", value)
                assert existing_props[prop_name] == value

            # Write property to rule
            existing_props[prop_name] = value
            properties[prop_name][value].append(sel_string)
            for selector in selectors:
                properties[prop_name][value].remove(selector)

            # Delete property from old rules
            for selector in selectors:
                rules[selector].pop(prop_name)
                # If it's empty, remove it entirely
                if not rules[selector]:
                    del rules[selector]

    # TODO: Would be nice to automatically seek out stuff we can efficiently
    # collapse, but for now, this achieves great gains for little complexity.

    # Remove all useless background-position's
    for selector in properties.get("background-position", {}).get("0px 0px", []):
        rules[selector].pop("background-position")
        if not rules[selector]:
            del rules[selector]
    if "0px 0px" in properties["background-position"]:
        del properties["background-position"]["0px 0px"]

    # Condense multi-emote spritesheets (probably most of our savings)
    for (image_url, selectors) in list(properties.get("background-image", {}).items()):
        if len(selectors) > 1:
            # For some reason, condensing these properties here gains more savings
            # than doing them separately. Oh well.
            condense({"background-image": image_url, "display": "block", "clear": "none", "float": "left"})
            #condense({"background-image": image_url})

    # Condense similar background-position's. Not likely to make a big difference
    # except for a few very similar spritesheet grids.
    for position in list(properties["background-position"]):
        condense({"background-position": position})

    # Condense by width/height, since many emotes have the same dimensions
    for (width, w_selectors) in [(w, s) for (w, s) in properties["width"].items() if len(s) > 1]:
        for (height, h_selectors) in [(h, s) for (h, s) in properties["height"].items() if len(s) > 1]:
            if any(s in h_selectors for s in w_selectors):
                condense({"height": height, "width": width})

    for width in properties["width"]:
        condense({"width": width})

    for height in properties["height"]:
        condense({"height": height})

    # Locate and combine identical rules
    for (selector, props) in rules.copy().items():
        condense(props.copy())

AutogenHeader = """
/*
 * This file is AUTOMATICALLY GENERATED. DO NOT EDIT.
 * Generated at %s.
 */

""" % (time.strftime("%c"))

def dump_css(file, rules):
    file.write(AutogenHeader)
    for (selector, properties) in rules.items():
        property_strings = ["%s:%s" % i for i in properties.items()]
        s = "%s{%s}\n" % (selector, ";".join(property_strings))
        file.write(s)

def dump_js(file, js_map):
    file.write(AutogenHeader)
    file.write("var emote_map = {\n")

    strings = ["%r:%r" % i for i in js_map.items()]
    file.write(",\n".join(strings))

    file.write("\n}\n")

### Main

def main():
    parser = argparse.ArgumentParser(description="Generate addon data files from emotes")
    parser.add_argument("-j", "--js", help="Output JS file", default="build/emote-map.js")
    parser.add_argument("-c", "--css", help="Output CSS file", default="build/emote-classes.css")
    parser.add_argument("-n", "--nsfw-css", help="Output NSFW CSS file", default="build/nsfw-emote-classes.css")
    parser.add_argument("-d", "--directives", help="Processing directives",
                        default="data/emote-directives.yaml", type=argparse.FileType("r"))
    parser.add_argument("emotes", help="Input emote files", nargs="+")
    args = parser.parse_args()

    files = {}

    print("Loading emotes")
    for (i, filename) in enumerate(args.emotes):
        with open(filename) as file:
            data = bplib.load_yaml_file(file)
            efile = EmoteFile.from_data(data)
            files[efile.meta["Name"]] = efile

    print("Processing")
    emotes = resolve_emotes(files, bplib.load_yaml_file(args.directives))
    css_rules, nsfw_css_rules = build_css(emotes)
    js_map = build_js(emotes)
    condense_css(css_rules)
    condense_css(nsfw_css_rules)

    print("Dumping")
    with open(args.css, "w") as file:
        dump_css(file, css_rules)
    with open(args.nsfw_css, "w") as file:
        dump_css(file, nsfw_css_rules)
    with open(args.js, "w") as file:
        dump_js(file, js_map)

if __name__ == "__main__":
    main()

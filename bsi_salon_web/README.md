# Enrich Beauty Website — `bsi_salon_web`

Odoo 19 module that installs the complete Enrich Beauty website.

## Install

1. Copy this folder to your addons path:

   ```
   /home/bsi/Documents/Enrich/bsi_salon_web
   ```

   Make sure `/home/bsi/Documents/Enrich` is listed in `addons_path` in your
   Odoo config, e.g.

   ```
   addons_path = /path/to/odoo/addons,/home/bsi/Documents/Enrich
   ```

2. Restart Odoo and update the apps list.
3. Install **Enrich Beauty Website**.

The default website homepage is repointed to `/salon` on install, so opening the
site shows the Enrich experience immediately. It is also reachable from the
**Enrich Website** app menu.

## Routes

| Route | Purpose |
|---|---|
| `/salon` | The site (single-page experience) |
| `/salon/stores`, `/salon/booking`, `/salon/membership`, `/salon/services`, `/salon/stylists`, `/salon/about`, `/salon/contact` | Deep links — all resolve to the same page so refreshes and shared URLs never 404 |

## How fidelity is guaranteed

The design is shipped as one self-contained asset at
`static/src/enrich_site.html` — markup, styles, scripts and every illustration
are inlined into that single file. The controller serves it verbatim.

Nothing is re-implemented as QWeb templates, which is what causes drift between
a design and its Odoo port. What renders in Odoo is byte-identical to the
approved design.

## Requires an internet connection

Three resources still load from their CDNs, exactly as in the approved design:

- Google Fonts (Playfair Display, Manrope)
- Leaflet 1.9.4 (the real store map)
- OpenStreetMap tiles
- three.js 0.184.0 (the 3D salon chairs)

## Editing the design later

Do not hand-edit `static/src/enrich_site.html` — it is compiled output. Change
the source design and re-export, replacing that one file.

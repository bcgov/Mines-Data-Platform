# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# CELL ********************

import geoanalytics_fabric
import geoanalytics_fabric.sql.functions as ST
from pyspark.sql import functions as F

print(f"GeoAnalytics for Fabric version: {geoanalytics_fabric.__version__}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

turbines_url = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "US_Wind_Turbine_Database/FeatureServer/0"
)
burn_areas_url = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "MTBS_Polygons_v1/FeatureServer/0"
)

turbines = spark.read.format("feature-service").load(turbines_url)
burn_areas = spark.read.format("feature-service").load(burn_areas_url)

print(f"Turbines:   {turbines.count():>8,} rows")
print(f"Burn areas: {burn_areas.count():>8,} rows")

turbines.printSchema()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

turbines.select(
    "case_id",
    "t_state",
    "t_cap",            # turbine capacity (kW)
    "p_year",           # year online
    ST.as_text("shape").alias("geometry_wkt"),
).show(5, truncate=80)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

ALBERS = 102008  # USA Contiguous Albers Equal Area Conic

turbines_p = (
    turbines
    .withColumn("geom", ST.transform("shape", ALBERS))
    .drop("shape")
)

burn_p = (
    burn_areas
    .withColumn("geom", ST.transform("shape", ALBERS))
    .drop("shape")
)

turbines_p.select("case_id", ST.srid("geom").alias("srid")).show(3)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

BUFFER_M = 10_000  # 10 km

turbines_buf = turbines_p.withColumn("buffer", ST.buffer("geom", BUFFER_M))

turbines_buf.select(
    "case_id",
    "t_state",
    ST.area("buffer").alias("buffer_area_m2"),
).show(5)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

turbines_p.createOrReplaceTempView("turbines")
burn_p.createOrReplaceTempView("burn_areas")

turbines_in_burns = spark.sql("""
    SELECT
        t.case_id,
        t.t_state,
        t.t_cap,
        b.Incid_Name  AS fire_name,
        b.Ig_Date     AS ignition_date,
        t.geom        AS geom
    FROM turbines t
    JOIN burn_areas b
      ON ST_Within(t.geom, b.geom)
""")

print(f"Turbines located inside a recorded burn area: {turbines_in_burns.count():,}")
turbines_in_burns.show(10, truncate=False)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

NEAR_M = 5_000

near_burns = (
    turbines_p.alias("t")
    .join(
        burn_p.alias("b"),
        ST.dwithin("t.geom", "b.geom", NEAR_M),
    )
    .select(
        F.col("t.case_id"),
        F.col("t.t_state"),
        F.col("b.Incid_Name").alias("fire_name"),
        ST.distance("t.geom", "b.geom").alias("distance_m"),
    )
)

near_burns.orderBy("distance_m").show(10)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

H3_RES = 4  # ~1,770 km² per cell — coarse, good for national view

# Re-project to WGS 84 for H3 (H3 expects lon/lat)
turbines_wgs = turbines_p.withColumn("geom_wgs", ST.transform("geom", 4326))

h3_summary = (
    turbines_wgs
    .withColumn("h3", ST.h3_bin("geom_wgs", H3_RES))
    .groupBy("h3")
    .agg(
        F.count("*").alias("turbine_count"),
        F.sum("t_cap").alias("total_capacity_kw"),
        F.avg("p_year").alias("avg_install_year"),
    )
    .orderBy(F.desc("turbine_count"))
)

h3_summary.show(10)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

h3_polygons = h3_summary.withColumn("hex_geom", ST.h3_to_polygon("h3"))

h3_polygons.select(
    "h3",
    "turbine_count",
    "total_capacity_kw",
    ST.as_text("hex_geom").alias("hex_wkt"),
).show(5, truncate=100)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Fabric Map Demo</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    #map { height: 520px; width: 100%; border-radius: 8px; }
    .legend {
      background: white; padding: 8px 12px; border-radius: 6px;
      font: 12px/1.4 -apple-system, system-ui, sans-serif;
      box-shadow: 0 1px 4px rgba(0,0,0,.2);
    }
    .legend .dot {
      display: inline-block; width: 10px; height: 10px;
      border-radius: 50%; margin-right: 6px; vertical-align: middle;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    // Sample wind farms — [name, lat, lon, capacity_MW]
    const farms = [
      ["Alta Wind Energy Center",       35.0149, -118.3209, 1548],
      ["Shepherds Flat Wind Farm",      45.6970, -120.1939,  845],
      ["Roscoe Wind Farm",              32.4540, -100.5390,  781],
      ["Horse Hollow Wind Energy",      32.2520,  -99.9580,  735],
      ["Capricorn Ridge Wind Farm",     31.9230, -100.9580,  662],
      ["Fowler Ridge Wind Farm",        40.6230,  -87.3210,  600],
      ["Meadow Lake Wind Farm",         40.7670,  -86.9090,  500],
      ["Smoky Hills Wind Farm",         38.8730,  -98.4640,  250]
    ];

    const map = L.map('map').setView([39.5, -98.5], 4);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18
    }).addTo(map);

    // Scale circle radius by capacity
    const colorFor = mw => mw > 1000 ? '#7e22ce'
                          : mw > 700  ? '#c026d3'
                          : mw > 500  ? '#db2777'
                          : '#f59e0b';

    farms.forEach(([name, lat, lon, mw]) => {
      L.circleMarker([lat, lon], {
        radius: Math.sqrt(mw) / 2,
        color: colorFor(mw),
        weight: 2,
        fillColor: colorFor(mw),
        fillOpacity: 0.5
      })
      .bindPopup(`<b>${name}</b><br>Capacity: ${mw} MW`)
      .addTo(map);
    });

    const legend = L.control({position: 'bottomright'});
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'legend');
      div.innerHTML = `
        <b>Capacity (MW)</b><br>
        <span class="dot" style="background:#7e22ce"></span> > 1000<br>
        <span class="dot" style="background:#c026d3"></span> 700 – 1000<br>
        <span class="dot" style="background:#db2777"></span> 500 – 700<br>
        <span class="dot" style="background:#f59e0b"></span> < 500
      `;
      return div;
    };
    legend.addTo(map);
  </script>
</body>
</html>
"""

displayHTML(html)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

html = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>US Mines & Mineral Resources Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    #map { height: 640px; width: 100%; border-radius: 8px; }
    .info-panel {
      background: white; padding: 10px 14px; border-radius: 6px;
      font-size: 13px; line-height: 1.5;
      box-shadow: 0 1px 6px rgba(0,0,0,.25);
      max-width: 260px;
    }
    .info-panel h4 {
      margin: 0 0 6px; color: #444;
      border-bottom: 1px solid #ddd; padding-bottom: 4px;
    }
    .legend i {
      width: 14px; height: 14px; float: left;
      margin-right: 8px; opacity: 0.85;
      border-radius: 50%;
    }
    .legend .swatch-line {
      display: inline-block; width: 18px; height: 3px;
      margin-right: 8px; vertical-align: middle;
    }
    .legend .swatch-poly {
      display: inline-block; width: 14px; height: 14px;
      margin-right: 8px; vertical-align: middle;
      border: 2px solid; opacity: 0.6;
    }
    .popup-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .popup-meta { color: #666; font-size: 12px; }
    .popup-stat { margin-top: 6px; }
    .popup-stat b { color: #222; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    // -----------------------------------------------------------------
    // SAMPLE DATA — illustrative US mining sites, districts, and routes
    // Locations are approximate, drawn from public USGS MRDS references
    // -----------------------------------------------------------------

    const mines = [
      // [name, lat, lon, commodity, type, production_tons_yr, status]
      ["Bingham Canyon Mine",   40.5230, -112.1505, "Copper",      "Open Pit",    280000, "Active"],
      ["Morenci Mine",          33.0489, -109.3650, "Copper",      "Open Pit",    900000, "Active"],
      ["Goldstrike Mine",       40.9430, -116.3590, "Gold",        "Open Pit",      1450, "Active"],
      ["Cortez Mine",           40.1730, -116.6260, "Gold",        "Underground",    900, "Active"],
      ["Red Dog Mine",          68.0750, -162.8580, "Zinc/Lead",   "Open Pit",    550000, "Active"],
      ["Greens Creek Mine",     58.0700, -134.6300, "Silver/Zinc", "Underground",  20000, "Active"],
      ["Stillwater Mine",       45.3850, -109.8770, "Palladium",   "Underground",    600, "Active"],
      ["Mountain Pass Mine",    35.4780, -115.5330, "Rare Earth",  "Open Pit",     43000, "Active"],
      ["Climax Mine",           39.3680, -106.1880, "Molybdenum",  "Open Pit",     30000, "Active"],
      ["Henderson Mine",        39.7700, -105.8920, "Molybdenum",  "Underground",  25000, "Active"],
      ["Cripple Creek & Victor",38.7270, -105.1430, "Gold",        "Open Pit",       350, "Active"],
      ["Twin Creeks Mine",      41.1660, -117.1610, "Gold",        "Open Pit",       950, "Active"],
      ["Continental Mine",      46.0080, -112.5390, "Copper/Moly", "Open Pit",     50000, "Active"],
      ["Eagle Mine",            46.7610,  -87.8810, "Nickel/Cu",   "Underground",  17000, "Active"],
      ["Lisbon Valley Mine",    38.2890, -109.2820, "Copper",      "Open Pit",      8000, "Care & Maintenance"],
      ["Berkeley Pit",          46.0156, -112.5114, "Copper",      "Open Pit",         0, "Closed (Flooded)"]
    ];

    // Mining districts — polygons drawn as approximate regional zones
    const districts = [
      {
        name: "Carlin Trend",
        commodity: "Gold",
        notes: "One of the world's most productive gold districts; trend of sediment-hosted deposits.",
        color: "#f59e0b",
        coords: [
          [41.30, -116.85], [41.30, -116.10],
          [40.05, -116.10], [40.05, -116.85]
        ]
      },
      {
        name: "Arizona Copper Belt",
        commodity: "Copper",
        notes: "Porphyry copper province; contains Morenci, Bagdad, Ray, and Sierrita mines.",
        color: "#c2410c",
        coords: [
          [34.50, -111.20], [34.50, -109.00],
          [32.00, -109.00], [32.00, -111.20]
        ]
      },
      {
        name: "Colorado Mineral Belt",
        commodity: "Mo / Au / Ag",
        notes: "NE-trending belt of intrusive-related deposits; includes Climax and Henderson.",
        color: "#7e22ce",
        coords: [
          [40.10, -107.20], [40.10, -105.10],
          [37.40, -106.20], [37.40, -107.80]
        ]
      },
      {
        name: "Stillwater Complex",
        commodity: "PGM",
        notes: "Only significant platinum-group metals producer in the United States.",
        color: "#0891b2",
        coords: [
          [45.55, -110.30], [45.55, -109.40],
          [45.20, -109.40], [45.20, -110.30]
        ]
      }
    ];

    // Concession / claim boundaries — irregular polygon
    const concession = {
      name: "Bingham Canyon Mining Claim",
      operator: "Rio Tinto Kennecott",
      area_acres: 8400,
      coords: [
        [40.560, -112.190], [40.560, -112.110],
        [40.540, -112.080], [40.500, -112.090],
        [40.485, -112.140], [40.510, -112.200]
      ]
    };

    // Transport routes — rail/road lines from mines to ports/smelters
    const transportRoutes = [
      {
        name: "Red Dog Haul Road",
        type: "Industrial Road",
        from: "Red Dog Mine", to: "DeLong Mountain Port",
        coords: [[68.0750, -162.8580], [67.7100, -163.7800], [67.5950, -164.6700]]
      },
      {
        name: "Bingham → Garfield Smelter",
        type: "Rail",
        from: "Bingham Canyon", to: "Garfield Smelter",
        coords: [[40.5230, -112.1505], [40.6300, -112.1700], [40.7320, -112.1830]]
      },
      {
        name: "Morenci Rail Spur",
        type: "Rail",
        from: "Morenci Mine", to: "Lordsburg Junction",
        coords: [[33.0489, -109.3650], [32.7000, -109.0400], [32.3500, -108.7100]]
      }
    ];

    // Exploration zones — circular buffer search areas
    const explorationZones = [
      { name: "Northern Nevada Au Search", lat: 41.50, lon: -116.50, radius_km: 80, color: "#eab308" },
      { name: "Arizona Cu Brownfield Buffer", lat: 33.20, lon: -110.50, radius_km: 120, color: "#dc2626" },
      { name: "Idaho REE Greenfield Target", lat: 44.20, lon: -114.30, radius_km: 95, color: "#7c3aed" }
    ];

    // -----------------------------------------------------------------
    // MAP SETUP
    // -----------------------------------------------------------------
    const map = L.map('map').setView([41.0, -110.0], 5);

    // Two basemap options users can switch between
    const streets = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors', maxZoom: 18
    });
    const topo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution: 'Map data: © OpenStreetMap, SRTM | © OpenTopoMap', maxZoom: 17
    });
    streets.addTo(map);

    // -----------------------------------------------------------------
    // LAYER 1 — Mining district polygons
    // -----------------------------------------------------------------
    const districtLayer = L.layerGroup();
    districts.forEach(d => {
      L.polygon(d.coords, {
        color: d.color, weight: 2, fillColor: d.color, fillOpacity: 0.18, dashArray: "4,4"
      })
      .bindPopup(`
        <div class="popup-title">${d.name}</div>
        <div class="popup-meta">Mining District</div>
        <div class="popup-stat"><b>Primary commodity:</b> ${d.commodity}</div>
        <div class="popup-stat" style="margin-top:6px;font-size:12px;color:#555;">${d.notes}</div>
      `)
      .addTo(districtLayer);
    });
    districtLayer.addTo(map);

    // -----------------------------------------------------------------
    // LAYER 2 — Mining claim / concession polygon (irregular shape)
    // -----------------------------------------------------------------
    const concessionLayer = L.polygon(concession.coords, {
      color: "#1f2937", weight: 2, fillColor: "#6b7280", fillOpacity: 0.35
    }).bindPopup(`
      <div class="popup-title">${concession.name}</div>
      <div class="popup-meta">Active Mining Claim</div>
      <div class="popup-stat"><b>Operator:</b> ${concession.operator}</div>
      <div class="popup-stat"><b>Area:</b> ${concession.area_acres.toLocaleString()} acres</div>
    `);
    concessionLayer.addTo(map);

    // -----------------------------------------------------------------
    // LAYER 3 — Exploration zones (circles in metres)
    // -----------------------------------------------------------------
    const explorationLayer = L.layerGroup();
    explorationZones.forEach(z => {
      L.circle([z.lat, z.lon], {
        radius: z.radius_km * 1000,
        color: z.color, weight: 2, fillColor: z.color, fillOpacity: 0.10, dashArray: "8,6"
      })
      .bindPopup(`
        <div class="popup-title">${z.name}</div>
        <div class="popup-meta">Exploration Buffer</div>
        <div class="popup-stat"><b>Search radius:</b> ${z.radius_km} km</div>
      `)
      .addTo(explorationLayer);
    });
    explorationLayer.addTo(map);

    // -----------------------------------------------------------------
    // LAYER 4 — Transport routes (polylines)
    // -----------------------------------------------------------------
    const routeLayer = L.layerGroup();
    transportRoutes.forEach(r => {
      const style = r.type === "Rail"
        ? { color: "#0f172a", weight: 3, dashArray: "1,6", lineCap: "round" }
        : { color: "#92400e", weight: 3 };
      L.polyline(r.coords, style)
        .bindPopup(`
          <div class="popup-title">${r.name}</div>
          <div class="popup-meta">${r.type}</div>
          <div class="popup-stat"><b>From:</b> ${r.from}</div>
          <div class="popup-stat"><b>To:</b> ${r.to}</div>
        `)
        .addTo(routeLayer);
    });
    routeLayer.addTo(map);

    // -----------------------------------------------------------------
    // LAYER 5 — Mine point markers, sized by production, coloured by commodity
    // -----------------------------------------------------------------
    const commodityColor = {
      "Copper":      "#c2410c",
      "Copper/Moly": "#b45309",
      "Gold":        "#f59e0b",
      "Silver/Zinc": "#94a3b8",
      "Zinc/Lead":   "#475569",
      "Palladium":   "#0891b2",
      "Rare Earth":  "#7e22ce",
      "Molybdenum":  "#a16207",
      "Nickel/Cu":   "#15803d"
    };

    const radiusFor = tons => {
      if (tons === 0)      return 6;
      if (tons < 1000)     return 8;
      if (tons < 50000)    return 11;
      if (tons < 200000)   return 14;
      return 18;
    };

    const statusStyle = status => {
      if (status === "Active") return { weight: 2, fillOpacity: 0.85 };
      if (status.startsWith("Care")) return { weight: 2, fillOpacity: 0.45, dashArray: "3,3" };
      return { weight: 2, fillOpacity: 0.25, dashArray: "3,3" };
    };

    const mineLayer = L.layerGroup();
    mines.forEach(([name, lat, lon, commodity, mineType, prod, status]) => {
      const color = commodityColor[commodity] || "#334155";
      L.circleMarker([lat, lon], {
        radius: radiusFor(prod),
        color: "#fff",
        fillColor: color,
        ...statusStyle(status)
      })
      .bindPopup(`
        <div class="popup-title">${name}</div>
        <div class="popup-meta">${mineType} · ${status}</div>
        <div class="popup-stat"><b>Commodity:</b> <span style="color:${color}">${commodity}</span></div>
        <div class="popup-stat"><b>Production:</b> ${prod ? prod.toLocaleString() + " t/yr" : "—"}</div>
        <div class="popup-stat"><b>Location:</b> ${lat.toFixed(3)}°, ${lon.toFixed(3)}°</div>
      `)
      .bindTooltip(name, { direction: "top", offset: [0, -8] })
      .addTo(mineLayer);
    });
    mineLayer.addTo(map);

    // -----------------------------------------------------------------
    // LEGEND
    // -----------------------------------------------------------------
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'info-panel legend');
      div.innerHTML = `
        <h4>Commodity</h4>
        <div><i style="background:#c2410c"></i> Copper</div>
        <div><i style="background:#f59e0b"></i> Gold</div>
        <div><i style="background:#94a3b8"></i> Silver / Zinc</div>
        <div><i style="background:#7e22ce"></i> Rare Earth</div>
        <div><i style="background:#a16207"></i> Molybdenum</div>
        <div><i style="background:#0891b2"></i> Palladium / PGM</div>
        <div><i style="background:#15803d"></i> Nickel / Cu</div>
        <div style="clear:both;margin-top:8px;border-top:1px solid #ddd;padding-top:6px;">
          <b>Shapes</b><br>
          <span class="swatch-poly" style="background:#f59e0b33;border-color:#f59e0b"></span> Mining district<br>
          <span class="swatch-poly" style="background:#6b728055;border-color:#1f2937"></span> Mining claim<br>
          <span class="swatch-poly" style="background:#dc262622;border-color:#dc2626;border-radius:50%"></span> Exploration buffer<br>
          <span class="swatch-line" style="background:#92400e"></span> Haul road<br>
          <span class="swatch-line" style="background:#0f172a;border-top:1px dashed #0f172a"></span> Rail
        </div>
        <div style="margin-top:8px;font-size:11px;color:#888;">
          Marker size ∝ annual production
        </div>
      `;
      return div;
    };
    legend.addTo(map);

    // -----------------------------------------------------------------
    // LAYER TOGGLE CONTROL
    // -----------------------------------------------------------------
    L.control.layers(
      { "Streets": streets, "Topographic": topo },
      {
        "Mines":              mineLayer,
        "Mining districts":   districtLayer,
        "Mining claim":       concessionLayer,
        "Exploration zones":  explorationLayer,
        "Transport routes":   routeLayer
      },
      { collapsed: false }
    ).addTo(map);

    // Scale bar
    L.control.scale({ imperial: true, metric: true }).addTo(map);
  </script>
</body>
</html>
"""

displayHTML(html)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

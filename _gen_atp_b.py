# -*- coding: utf-8 -*-
import json, io, os

R = {}
def a(code, anchors, why, conf="high"):
    R[code] = {"anchors": anchors, "why": why, "confidence": conf}

# ---- Task A: Preflight Assessment ----
a("AA.II.A.K1", ["aim:ch08-s01", "phak:ch17", "risk-management:ch02"],
  "AIM 8-1 Fitness for Flight and PHAK ch17 carry IMSAFE; RMH ch02 Personal Minimums is the self-assessment chapter")
a("AA.II.A.K2", ["phak:ch09"],
  "PHAK ch09 Flight Manuals and Other Documents is the chapter that locates and explains the airworthiness paperwork")
a("AA.II.A.K2a", ["phak:ch09"],
  "PHAK ch09 covers the airworthiness and registration certificates directly, 18 hits on pages 237 to 243")
a("AA.II.A.K2b", ["phak:ch09"],
  "PHAK ch09 is the AFM/POH and operating limitations chapter")
a("AA.II.A.K2c", ["phak:ch09"],
  "PHAK ch09 pages 239 to 240 treat the Minimum Equipment List and inoperative equipment")
a("AA.II.A.K2d", ["phak:ch10", "phak:ch09"],
  "PHAK ch10 Weight and Balance holds the data itself; ch09 covers where the loading documents live")
a("AA.II.A.K2e", ["phak:ch09"],
  "PHAK ch09 covers required inspections, records, and the special flight permit")
a("AA.II.A.K3", ["phak:ch09"],
  "PHAK ch09 carries preventive maintenance, 15 hits on pages 235 to 241")
a("AA.II.A.K4", ["afh:ch02", "seaplane:preflight-inspection"],
  "AFH ch02 Ground Operations is the preflight inspection chapter; the Seaplane preflight section covers the float-specific items")
a("AA.II.A.K4a", ["afh:ch02", "seaplane:preflight-inspection"],
  "AFH ch02 lists what a visual preflight inspects; the Seaplane preflight section adds hull, floats, and water rudders")
a("AA.II.A.K4b", ["afh:ch02"],
  "AFH ch02 gives the reason behind each preflight item, pages 38 to 44")
a("AA.II.A.K4c", ["afh:ch02"],
  "AFH ch02 covers detecting defects during the visual preflight")
a("AA.II.A.K4d", ["phak:ch09"],
  "PHAK ch09 is where the inspection and airworthiness regulations are explained")
a("AA.II.A.K5", ["aim:ch05-s01", "aviation-weather:ch03"],
  "AIM 5-1 Preflight is the preflight planning section; AWH ch03 Overview of Aviation Weather Information covers the weather side")
a("AA.II.A.K6", ["aim:ch09-s01", "phak:ch16"],
  "AIM 9-1 Types of Charts Available covers chart currency; PHAK ch16 Navigation covers navigation data and effective dates")
a("AA.II.A.K7", [],
  "No chapter treats operations specifications or letters of authorization as its subject. The document-level rows stay")
a("AA.II.A.R1", ["aim:ch08-s01", "phak:ch02"],
  "AIM 8-1 Fitness for Flight and PHAK ch02 Aeronautical Decision-Making carry the human factors material, 14 hits in ch02")
a("AA.II.A.R2", ["phak:ch09"],
  "PHAK ch09 pages 231 to 240 cover inoperative equipment and MEL relief found before flight")
a("AA.II.A.R3", ["aim:ch07-s06", "risk-management:ch03"],
  "AIM 7-6 Potential Flight Hazards names the environmental hazards; RMH ch03 Identifying Hazards is the assessment chapter")
a("AA.II.A.R4", ["phak:ch02", "risk-management:ch03"],
  "PHAK ch02 has 17 hits on external pressures; RMH ch03 Identifying Hazards covers the PAVE external pressure element")
a("AA.II.A.R5", ["aim:ch05-s06"],
  "AIM 5-6 National Security and Interception Procedures is the security section, 76 hits")
a("AA.II.A.S1", ["afh:ch02", "seaplane:preflight-inspection"],
  "AFH ch02 covers the checklist-driven preflight inspection; the Seaplane preflight section covers the seaplane checklist")
a("AA.II.A.S2", ["afh:ch02"],
  "AFH ch02 pages 52 and 56 cover ground crew coordination and clearance around the airplane")
a("AA.II.A.S3", ["phak:ch09"],
  "PHAK ch09 covers discrepancy records and the limitations an MEL item imposes")
a("AA.II.A.S4", ["phak:ch09"],
  "PHAK ch09 is where airworthy and condition for safe flight is defined and documented")
a("AA.II.A.S5", [],
  "No chapter treats operations specifications as its subject. The document-level rows stay")
a("AA.II.A.S6", ["aim:ch07-s06", "aviation-weather:ch03"],
  "AIM 7-6 Potential Flight Hazards covers the environmental assessment; AWH ch03 covers assembling the weather picture")
a("AA.II.A.S7", ["phak:ch07", "aviation-weather:ch20"],
  "PHAK ch07 Aircraft Systems holds the deice and anti-ice material, 18 hits; AWH ch20 Icing covers the contamination itself")

# ---- Task B: Powerplant Start ----
a("AA.II.B.K1", ["afh:ch02", "afh:ch16"],
  "AFH ch02 Ground Operations has 15 hits on engine start; ch16 Transition to Jet-Powered Airplanes covers the APU start")
a("AA.II.B.K2", ["afh:ch02"],
  "AFH ch02 pages 53 to 54 cover starting under hot, cold, and flooded conditions")
a("AA.II.B.K3", ["afh:ch02", "afh:ch18"],
  "AFH ch02 covers start malfunctions; ch18 Emergency Procedures covers the engine fire during start")
a("AA.II.B.K4", ["afh:ch02"],
  "AFH ch02 pages 52 and 56 cover ground crew signals and coordination for start")
a("AA.II.B.R1", ["afh:ch02", "afh:ch18"],
  "AFH ch02 covers the start malfunction and ch18 the emergency it can become")
a("AA.II.B.R2", ["afh:ch02"],
  "AFH ch02 Ground Operations is the propeller and engine ramp safety chapter")
a("AA.II.B.R3", ["risk-management:ch08"],
  "RMH ch08 Aeronautical Decision-Making has 27 checklist hits and covers deciding where no procedure is published")
a("AA.II.B.R4", ["afh:ch02"],
  "AFH ch02 covers clearing the area of persons, vehicles, and debris before start")
a("AA.II.B.S1", ["afh:ch02"],
  "AFH ch02 Ground Operations covers before-start, start, and after-start ground safety")
a("AA.II.B.S2", ["afh:ch02"],
  "AFH ch02 covers use of ground crew during the start procedure")
a("AA.II.B.S3", ["afh:ch02"],
  "AFH ch02 covers checklist use around the start sequence")
a("AA.II.B.S4", ["afh:ch02", "afh:ch18"],
  "AFH ch02 gives the abnormal start response and ch18 the emergency procedure if it escalates")

# ---- Task C: Taxiing ----
a("AA.II.C.K1", ["aim:ch05-s01", "aim:ch09-s01", "phak:ch14"],
  "AIM 5-1 Preflight holds the NOTAM material with 104 hits, 9-1 the chart types, and PHAK ch14 the Chart Supplement")
a("AA.II.C.K2", ["aim:ch04-s03"],
  "AIM 4-3 Airport Operations is the taxi clearance and published taxi route section")
a("AA.II.C.K3", ["aim:ch02-s01", "aim:ch02-s03", "phak:ch14"],
  "AIM 2-1 Airport Lighting Aids and 2-3 Airport Marking Aids and Signs; PHAK ch14 covers the same, 28 hits")
a("AA.II.C.K4", ["aim:ch04-s03", "afh:ch11"],
  "AIM 4-3 covers aircraft lights on the airport surface, page 266; AFH ch11 Night Operations covers night lighting use")
a("AA.II.C.K5", [],
  "Push-back gets one incidental AIM mention and no chapter treatment. The document-level rows stay")
a("AA.II.C.K6", ["aim:ch04-s03"],
  "AIM 4-3 Airport Operations covers taxi route planning, hot spots, and the airport diagram, pages 256 to 263")
a("AA.II.C.K7", ["aim:ch04-s02", "aim:ch04-s03", "phak:ch14"],
  "AIM 4-2 is the phraseology section and 4-3 covers towered and nontowered operations; PHAK ch14 has 28 comm hits")
a("AA.II.C.K8", ["aim:ch04-s03", "phak:ch14"],
  "AIM 4-3 covers hold short and runway crossing; PHAK ch14 covers holding position markings")
a("AA.II.C.K9", ["aim:ch04-s03", "afh:ch11"],
  "AIM 4-3 covers surface operations and AFH ch11 Night Operations covers taxiing at night, pages 222 and 225")
a("AA.II.C.K10", ["aim:ch04-s03"],
  "AIM 4-3 holds the low visibility and SMGCS material, 8 hits on pages 259 to 263")
a("AA.II.C.K11", ["afh:ch13"],
  "AFH ch13 Transition to Multiengine Airplanes covers differential power and braking on the ground, pages 263 and 271")
a("AA.II.C.R1", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management is the distraction and situational awareness chapter")
a("AA.II.C.R2", ["risk-management:ch06"],
  "RMH ch06 holds the expectation and confirmation bias material, 10 hits on pages 45 to 46")
a("AA.II.C.R3", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management covers the late change as a threat to be managed")
a("AA.II.C.R4", ["risk-management:ch06"],
  "RMH ch06 covers interrupted and partially completed checklists as an error trap")
a("AA.II.C.R5", ["aim:ch04-s03"],
  "AIM 4-3 is the low visibility surface operations section")
a("AA.II.C.R6", ["aim:ch04-s03", "phak:ch14"],
  "AIM 4-3 covers surface incursion avoidance; PHAK ch14 has 16 runway incursion hits")
a("AA.II.C.S1", ["aim:ch04-s03"],
  "AIM 4-3 covers receiving, reading back, and reviewing taxi instructions")
a("AA.II.C.S2", ["aim:ch09-s01"],
  "AIM 9-1 Types of Charts Available covers the airport diagram and taxi chart")
a("AA.II.C.S3", ["aim:ch02-s03", "aim:ch04-s03"],
  "AIM 2-3 covers hold lines, ILS critical area markings, and signs; 4-3 covers complying with ATC on the surface")
a("AA.II.C.S4", ["afh:ch02"],
  "AFH ch02 Ground Operations covers checklist use before and during taxi")
a("AA.II.C.S5", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management is the situational awareness chapter")
a("AA.II.C.S6", ["afh:ch02", "aim:ch04-s03"],
  "AFH ch02 has 18 taxi hits covering control, speed, and braking; AIM 4-3 covers separation on the surface")
a("AA.II.C.S7", ["afh:ch11", "aim:ch04-s03"],
  "AFH ch11 Night Operations covers night taxi; AIM 4-3 covers the daytime surface procedure")
a("AA.II.C.S8", ["aim:ch04-s03", "afh:ch11"],
  "AIM 4-3 page 266 covers aircraft light use on the surface; AFH ch11 covers night lighting")
a("AA.II.C.S9", ["aim:ch04-s03"],
  "AIM 4-3 covers the hazards of low visibility surface movement")

# ---- Task D: Taxiing and Sailing ----
a("AA.II.D.K1", ["aim:ch09-s01", "aim:ch05-s01", "phak:ch14"],
  "AIM 9-1 covers chart types, 5-1 the NOTAMs and preflight information, PHAK ch14 the Chart Supplement")
a("AA.II.D.K2", ["aim:ch04-s03"],
  "AIM 4-3 Airport Operations is the taxi clearance section")
a("AA.II.D.K3", ["aim:ch02-s03", "phak:ch14"],
  "AIM 2-3 Airport Marking Aids and Signs and PHAK ch14 Airport Operations carry the markings, signs, and lights")
a("AA.II.D.K4", ["aim:ch04-s03", "afh:ch11"],
  "AIM 4-3 page 266 covers aircraft lights on the surface; AFH ch11 Night Operations covers night use")
a("AA.II.D.K5", ["seaplane:sailing", "seaplane:taxiing-and-sailing"],
  "The Seaplane Handbook SAILING section is the sailing technique text, with TAXIING AND SAILING as its parent")
a("AA.II.D.K6", ["seaplane:sailing"],
  "The SAILING section covers choosing the sailing course for wind and current")
a("AA.II.D.K7", ["aim:ch04-s03", "seaplane:taxiing-and-sailing"],
  "AIM 4-3 covers airport surface procedures and the Seaplane TAXIING AND SAILING section the water equivalent")
a("AA.II.D.K7a", ["aim:ch04-s03"],
  "AIM 4-3 covers route planning and flight deck activity before taxi")
a("AA.II.D.K7b", ["aim:ch04-s02"],
  "AIM 4-2 Radio Communications Phraseology and Techniques covers towered and nontowered communication")
a("AA.II.D.K7c", ["aim:ch04-s03"],
  "AIM 4-3 covers entering and crossing runways")
a("AA.II.D.K7d", ["afh:ch11", "aim:ch04-s03"],
  "AFH ch11 Night Operations covers night taxi; the Seaplane Handbook has no night section, so nothing is proposed there")
a("AA.II.D.K7e", ["aim:ch04-s03"],
  "AIM 4-3 is the low visibility surface operations section")
a("AA.II.D.R1", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management is the distraction and situational awareness chapter")
a("AA.II.D.R2", ["seaplane:porpoising", "seaplane:skipping"],
  "The Seaplane Handbook has a section each for PORPOISING and SKIPPING")
a("AA.II.D.R3", ["risk-management:ch06"],
  "RMH ch06 covers interrupted and partially completed checklists")
a("AA.II.D.R4", ["aim:ch04-s03"],
  "AIM 4-3 holds the low visibility surface material")
a("AA.II.D.R5", ["seaplane:taxiing-and-sailing"],
  "TAXIING AND SAILING is the closest section for traffic and hazards on the water; vessel right-of-way is scattered, not sectioned", "low")
a("AA.II.D.R6", ["seaplane:amphibious-gear"],
  "The amphibious gear passage is the anchor for gear position in an amphibian")
a("AA.II.D.R7", ["risk-management:ch06"],
  "RMH ch06 holds the expectation and confirmation bias material")
a("AA.II.D.S1", ["aim:ch04-s03"],
  "AIM 4-3 covers receiving, reading back, and reviewing taxi instructions")
a("AA.II.D.S2", ["aim:ch09-s01"],
  "AIM 9-1 Types of Charts Available covers the airport diagram and taxi chart")
a("AA.II.D.S3", ["aim:ch02-s03"],
  "AIM 2-3 Airport Marking Aids and Signs covers the markings, signals, and signs to comply with")
a("AA.II.D.S4", ["seaplane:docking", "seaplane:mooring", "seaplane:beaching", "seaplane:ramping"],
  "The Seaplane Handbook has a section each for DOCKING, MOORING, BEACHING, and RAMPING, which is exactly this element")
a("AA.II.D.S5", ["afh:ch02"],
  "AFH ch02 Ground Operations covers checklist use before and during taxi")
a("AA.II.D.S6", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management is the situational awareness chapter")
a("AA.II.D.S7", ["seaplane:taxiing-and-sailing"],
  "TAXIING AND SAILING covers control, speed, and separation while maneuvering on the water")
a("AA.II.D.S8", ["seaplane:using-water-rudders", "seaplane:porpoising", "seaplane:skipping"],
  "USING WATER RUDDERS covers control and rudder position; PORPOISING and SKIPPING cover preventing and correcting each")
a("AA.II.D.S9", ["seaplane:idling-position", "seaplane:plowing-position", "seaplane:planing-or-step-position"],
  "The three taxi attitudes have a section each: IDLING POSITION, PLOWING POSITION, PLANING OR STEP POSITION")
a("AA.II.D.S10", ["seaplane:taxiing-and-sailing", "seaplane:turns"],
  "TAXIING AND SAILING covers steering and path control; TURNS covers maneuvering the seaplane on the water")
a("AA.II.D.S11", ["seaplane:sailing"],
  "SAILING covers planning the course that wind and current allow")
a("AA.II.D.S12", ["afh:ch11"],
  "AFH ch11 Night Operations covers night surface movement; the Seaplane Handbook has no night section")
a("AA.II.D.S13", ["aim:ch04-s03", "afh:ch11"],
  "AIM 4-3 page 266 covers aircraft light use on the surface; AFH ch11 covers night lighting")
a("AA.II.D.S14", ["aim:ch04-s03"],
  "AIM 4-3 covers the hazards of low visibility surface movement")

# ---- Task E: Before Takeoff Check ----
a("AA.II.E.K1", ["afh:ch02"],
  "AFH ch02 Ground Operations holds the before takeoff check, page 58 onward")
a("AA.II.E.K1a", ["afh:ch02"],
  "AFH ch02 gives the reason behind each before takeoff item")
a("AA.II.E.K1b", ["afh:ch02"],
  "AFH ch02 covers detecting malfunctions during the runup and before takeoff check")
a("AA.II.E.K1c", ["afh:ch02"],
  "AFH ch02 covers confirming the airplane is in safe operating condition before takeoff")
a("AA.II.E.K2", ["phak:ch07"],
  "PHAK ch07 Aircraft Systems holds the deice and anti-ice material, 18 hits; AFH has no holdover time text at all")
a("AA.II.E.K3", ["afh:ch06", "phak:ch11"],
  "AFH ch06 Takeoffs and Departure Climbs covers adverse condition takeoffs; PHAK ch11 Aircraft Performance covers the numbers")
a("AA.II.E.K4", ["afh:ch02"],
  "AFH ch02 page 59 carries the takeoff briefing and the V-speeds it states")
a("AA.II.E.R1", ["risk-management:ch06"],
  "RMH ch06 Threat and Error Management is the distraction and division of attention chapter")
a("AA.II.E.R2", ["risk-management:ch06"],
  "RMH ch06 covers the late runway change as a threat to be managed")
a("AA.II.E.R3", ["phak:ch11"],
  "PHAK ch11 Aircraft Performance is the takeoff performance data chapter")
a("AA.II.E.R4", ["risk-management:ch07"],
  "RMH ch07 Automation and Flight Path is the avionics setup chapter, 38 automation hits")
a("AA.II.E.R5", ["risk-management:ch07"],
  "RMH ch07 Automation and Flight Path covers autopilot and flight director configuration")
a("AA.II.E.R6", ["afh:ch06", "phak:ch11"],
  "AFH ch06 covers crosswind, contaminated, and low visibility takeoffs; PHAK ch11 covers the performance penalty")
a("AA.II.E.R7", ["afh:ch18", "afh:ch13"],
  "AFH ch18 Emergency Procedures covers powerplant failure on takeoff; ch13 covers the multiengine case and its V-speeds")
a("AA.II.E.S1", ["phak:ch11"],
  "PHAK ch11 Aircraft Performance is where takeoff distance for actual conditions is computed")
a("AA.II.E.S2", ["afh:ch02"],
  "AFH ch02 Ground Operations holds the before takeoff checklist")
a("AA.II.E.S3", ["afh:ch02", "phak:ch07"],
  "AFH ch02 covers the systems check itself; PHAK ch07 Aircraft Systems explains the operating characteristics and limits")
a("AA.II.E.S4", ["risk-management:ch07", "phak:ch11"],
  "RMH ch07 covers configuring flight director, autopilot, nav, and comm; PHAK ch11 supplies the V-speeds to set")
a("AA.II.E.S5", ["afh:ch18"],
  "AFH ch18 Emergency Procedures covers the powerplant failure and windshear cases the briefing must state")
a("AA.II.E.S6", [],
  "The AIM is not in this Task's references, and no AFH, PHAK, RMH, or Seaplane chapter covers departure clearances")

pkt = json.load(io.open('crosswalk/proposals/packets/atp-b.json', encoding='utf-8'))
menu = pkt['anchor_menu']
valid = set()
for doc, ch in menu.items():
    valid.update(ch.keys())
els = pkt['elements']

errs = []
missing = sorted(set(els) - set(R))
extra = sorted(set(R) - set(els))
if missing: errs.append('MISSING: %s' % missing)
if extra: errs.append('EXTRA: %s' % extra)
for code, v in R.items():
    if code not in els: continue
    refs = set(els[code]['references'])
    for an in v['anchors']:
        if an not in valid: errs.append('%s: anchor not in menu: %s' % (code, an))
        elif an.split(':')[0] not in refs: errs.append('%s: doc not in references: %s' % (code, an))
    if len(v['why']) > 160: errs.append('%s: why too long (%d)' % (code, len(v['why'])))
    if '—' in v['why'] or '–' in v['why']: errs.append('%s: dash' % code)

if errs:
    print('\n'.join(errs))
else:
    with io.open('crosswalk/proposals/rerun/atp-b.result.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write('\n')
    n_anch = sum(1 for v in R.values() if v['anchors'])
    print('OK wrote %d entries, %d with anchors, %d empty, low-conf %d' % (
        len(R), n_anch, len(R) - n_anch,
        sum(1 for v in R.values() if v['confidence'] == 'low')))

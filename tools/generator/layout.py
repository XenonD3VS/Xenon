"""Floor plans of xenon_police.

Local building frame: X east, Y north, Z up. Units = metres.
Main building footprint X 0..56, Y 0..36 (3 storeys, 4.2 m each),
single-storey garage annex X 15..56, Y 36..50. Main entrance on the south facade (Y = 0).
"""
from dataclasses import dataclass, field

FLOOR_H = 4.2
CEIL_H = 3.3          # suspended ceiling height above finished floor
DOOR_H = 2.5
LEVEL_Z = [0.0, 4.2, 8.4, 12.6]   # L1, L2, L3, roof
LEVEL_NAMES = ["L1", "L2", "L3", "ROOF"]
EXT_T = 0.3           # exterior wall thickness (outside the room rectangles)
INT_T = 0.15          # interior partition thickness (centred on boundary)

# room type -> (floor material, wall material, ceiling material, zone)
ROOM_TYPES = {
    "lobby":            ("lspd_terrazzo", "lspd_paint_white", "lspd_ceiling", "public"),
    "report":           ("lspd_carpet_grey", "lspd_paint_white", "lspd_ceiling", "public"),
    "interview_public": ("lspd_carpet_grey", "lspd_paint_blue", "lspd_ceiling", "public"),
    "wc_public":        ("lspd_tile_dark", "lspd_tile_white", "lspd_ceiling", "public"),
    "checkpoint":       ("lspd_terrazzo", "lspd_paint_grey", "lspd_ceiling", "secure"),
    "front_desk":       ("lspd_vinyl", "lspd_paint_white", "lspd_ceiling", "staff"),
    "records_counter":  ("lspd_vinyl", "lspd_paint_white", "lspd_ceiling", "staff"),
    "security_office":  ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "secure"),
    "office":           ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "staff"),
    "office_cmd":       ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "staff"),
    "office_exec":      ("lspd_wood_floor", "lspd_wood_veneer", "lspd_ceiling", "staff"),
    "admin":            ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "staff"),
    "conference":       ("lspd_carpet_navy", "lspd_wood_veneer", "lspd_ceiling", "staff"),
    "meeting":          ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "staff"),
    "officers":         ("lspd_carpet_grey", "lspd_paint_white", "lspd_ceiling", "staff"),
    "corridor":         ("lspd_vinyl", "lspd_paint_white", "lspd_ceiling", "staff"),
    "stair":            ("lspd_concrete", "lspd_paint_grey", "lspd_concrete", "staff"),
    "briefing":         ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "staff"),
    "patrol_bullpen":   ("lspd_carpet_grey", "lspd_paint_white", "lspd_ceiling", "staff"),
    "armory":           ("lspd_epoxy", "lspd_block", "lspd_concrete", "secure"),
    "equipment":        ("lspd_epoxy", "lspd_block", "lspd_ceiling", "secure"),
    "riot":             ("lspd_epoxy", "lspd_block", "lspd_concrete", "secure"),
    "maintenance":      ("lspd_epoxy", "lspd_block", "lspd_concrete", "technical"),
    "booking":          ("lspd_vinyl", "lspd_block", "lspd_ceiling", "detention"),
    "mugshot":          ("lspd_vinyl", "lspd_block", "lspd_ceiling", "detention"),
    "fingerprint":      ("lspd_vinyl", "lspd_block", "lspd_ceiling", "detention"),
    "property":         ("lspd_vinyl", "lspd_block", "lspd_ceiling", "detention"),
    "detention_control": ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "detention"),
    "detention_corridor": ("lspd_concrete", "lspd_block", "lspd_concrete", "detention"),
    "cell":             ("lspd_concrete", "lspd_block", "lspd_concrete", "detention"),
    "cell_hs":          ("lspd_concrete", "lspd_block", "lspd_concrete", "detention"),
    "sallyport":        ("lspd_epoxy", "lspd_block", "lspd_concrete", "detention"),
    "vehicle_intake":   ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "staff"),
    "garage":           ("lspd_epoxy", "lspd_concrete", "lspd_concrete", "technical"),
    "interrogation":    ("lspd_vinyl", "lspd_acoustic", "lspd_ceiling", "investigation"),
    "observation":      ("lspd_carpet_grey", "lspd_paint_navy", "lspd_ceiling", "investigation"),
    "case_room":        ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "investigation"),
    "lineup":           ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "investigation"),
    "lineup_view":      ("lspd_carpet_grey", "lspd_paint_navy", "lspd_ceiling", "investigation"),
    "evidence":         ("lspd_epoxy", "lspd_block", "lspd_ceiling", "secure"),
    "dispatch":         ("lspd_carpet_navy", "lspd_paint_navy", "lspd_ceiling", "secure"),
    "dispatch_super":   ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "secure"),
    "radio":            ("lspd_carpet_grey", "lspd_paint_grey", "lspd_ceiling", "secure"),
    "analysis":         ("lspd_carpet_navy", "lspd_paint_white", "lspd_ceiling", "investigation"),
    "detectives":       ("lspd_carpet_grey", "lspd_paint_white", "lspd_ceiling", "investigation"),
    "lab":              ("lspd_vinyl", "lspd_paint_white", "lspd_ceiling", "investigation"),
    "archive":          ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "technical"),
    "documents":        ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "technical"),
    "server":           ("lspd_vinyl", "lspd_paint_grey", "lspd_ceiling", "technical"),
    "technical":        ("lspd_concrete", "lspd_block", "lspd_concrete", "technical"),
    "janitor":          ("lspd_concrete", "lspd_block", "lspd_concrete", "technical"),
    "locker":           ("lspd_tile_dark", "lspd_paint_white", "lspd_ceiling", "staff"),
    "showers":          ("lspd_tile_white", "lspd_tile_white", "lspd_ceiling", "staff"),
    "break":            ("lspd_wood_floor", "lspd_paint_white", "lspd_ceiling", "staff"),
    "kitchen":          ("lspd_tile_white", "lspd_tile_white", "lspd_ceiling", "staff"),
    "dining":           ("lspd_wood_floor", "lspd_paint_white", "lspd_ceiling", "staff"),
    "gym":              ("lspd_rubber", "lspd_paint_grey", "lspd_concrete", "staff"),
}

ZONE_COLORS = {
    "public": (120, 190, 255), "staff": (170, 220, 170), "secure": (250, 200, 110),
    "investigation": (210, 170, 240), "detention": (250, 140, 140), "technical": (190, 190, 190),
}


@dataclass
class Room:
    rid: str
    level: int
    rtype: str
    rects: list
    title: str
    sign: str = None
    ceil: float = CEIL_H
    mlo_room: str = None   # filled later
    idx: int = -1

    @property
    def mats(self):
        return ROOM_TYPES[self.rtype]

    @property
    def zone(self):
        return ROOM_TYPES[self.rtype][3]

    def bbox(self):
        xs = [r[0] for r in self.rects] + [r[2] for r in self.rects]
        ys = [r[1] for r in self.rects] + [r[3] for r in self.rects]
        return min(xs), min(ys), max(xs), max(ys)

    def area(self):
        return sum((r[2] - r[0]) * (r[3] - r[1]) for r in self.rects)

    def contains(self, x, y):
        return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in self.rects)


@dataclass
class Door:
    level: int
    x: float
    y: float
    orient: str        # 'h' = in a wall parallel to X (constant y), 'v' = wall parallel to Y (constant x)
    width: float = 1.3
    kind: str = "std"  # std | glass | sec | cell | cell_hs | open | auto | vehicle | exit
    height: float = DOOR_H
    model: str = None


@dataclass
class Window:
    level: int
    orient: str        # 'h' wall at constant y, 'v' wall at constant x
    pos: float         # the constant coordinate (y for 'h', x for 'v')
    a: float           # start along wall
    b: float           # end along wall
    sill: float = 0.9
    head: float = 2.8
    kind: str = "ext"  # ext | mirror | glass | counter | curtain


ROOMS = []
DOORS = []
WINDOWS = []


def R(rid, level, rtype, rects, title, sign=None, ceil=CEIL_H):
    if isinstance(rects[0], (int, float)):
        rects = [rects]
    ROOMS.append(Room(rid, level, rtype, [tuple(float(v) for v in r) for r in rects], title, sign, ceil))


def D(level, x, y, orient, kind="std", width=None, height=DOOR_H):
    if width is None:
        width = {"std": 1.3, "glass": 1.3, "sec": 1.3, "cell": 1.2, "cell_hs": 1.2, "open": 1.6,
                 "auto": 3.0, "vehicle": 5.0, "exit": 1.3}[kind]
    if kind == "vehicle":
        height = 3.8
    DOORS.append(Door(level, float(x), float(y), orient, float(width), kind, height))


def W(level, orient, pos, a, b, sill=0.9, head=2.8, kind="ext"):
    WINDOWS.append(Window(level, orient, float(pos), float(a), float(b), sill, head, kind))


def split_windows(level, orient, pos, a, b, n, gap=0.6, **kw):
    w = (b - a - gap * (n - 1)) / n
    for i in range(n):
        s = a + i * (w + gap)
        W(level, orient, pos, s, s + w, **kw)


# =============================================================== LEVEL 1
L = 0
R("report", L, "report", (0, 0, 10, 6), "Report Room", "REPORT ROOM")
R("wc_m", L, "wc_public", (0, 6, 10, 12), "Public Restroom (M)", "RESTROOMS")
R("lobby", L, "lobby", (10, 0, 48, 12), "Public Lobby", "PUBLIC LOBBY", ceil=3.6)
R("interview_pub", L, "interview_public", (48, 0, 56, 6), "Citizen Interview", "INTERVIEW")
R("wc_w", L, "wc_public", (48, 6, 56, 12), "Public Restroom (W)", "RESTROOMS")
R("security", L, "security_office", (0, 12, 10, 18), "Security Office", "SECURITY CHECK")
R("records", L, "records_counter", (10, 12, 22, 18), "Records / Citizen Services", "CITIZEN SERVICES")
R("front_desk", L, "front_desk", (22, 12, 34, 18), "Front Desk / Reception", "RECEPTION")
R("checkpoint", L, "checkpoint", (34, 12, 37.5, 18), "Security Checkpoint", "AUTHORIZED PERSONNEL ONLY")
R("watch_cmd", L, "office_cmd", (37.5, 12, 46, 18), "Watch Commander", "WATCH COMMANDER")
R("sgt", L, "office", (46, 12, 56, 18), "Patrol Sergeants", "SERGEANT")
R("corr1", L, "corridor", (0, 18, 56, 20.4), "Main Corridor L1")
R("stair_a1", L, "stair", (0, 20.4, 3.4, 28), "Stair A", "STAIRS")
R("stair_b1", L, "stair", (52.6, 20.4, 56, 28), "Stair B", "STAIRS")
R("briefing", L, "briefing", (3.4, 20.4, 15, 28), "Briefing Room", "BRIEFING ROOM")
R("bullpen", L, "patrol_bullpen", (0, 28, 15, 36), "Patrol Report Room", "PATROL")
R("corr1b", L, "corridor", (15, 20.4, 17.4, 36), "Service Corridor")
R("armory", L, "armory", (17.4, 20.4, 25, 27), "Armory", "ARMORY")
R("equipment", L, "equipment", (17.4, 27, 25, 31.5), "Equipment & Vests", "EQUIPMENT")
R("riot", L, "riot", (17.4, 31.5, 21, 36), "Riot Gear Storage", "RIOT GEAR")
R("maint", L, "maintenance", (21, 31.5, 25, 36), "Equipment Maintenance", "MAINTENANCE")
R("booking", L, "booking", (25, 20.4, 33, 28), "Booking", "BOOKING")
R("mugshot", L, "mugshot", (33, 20.4, 38, 23), "Mugshot Room", "MUGSHOT")
R("fingerprint", L, "fingerprint", (33, 23, 38, 25.6), "Fingerprinting", "FINGERPRINTS")
R("property", L, "property", (33, 25.6, 38, 28), "Property Check", "PROPERTY")
R("det_control", L, "detention_control", (38, 20.4, 45, 28), "Detention Control", "CONTROL ROOM")
R("intake", L, "vehicle_intake", (45, 20.4, 52.6, 28), "Vehicle Intake Office", "VEHICLE INTAKE")
R("cellcorr", L, "detention_corridor", (25, 28, 45, 30.4), "Cell Block Corridor", "CELL BLOCK")
for i, (x0, x1) in enumerate([(25, 28.5), (28.5, 32), (32, 35.5), (35.5, 39)]):
    R(f"cell{i + 1}", L, "cell", (x0, 30.4, x1, 36), f"Holding Cell {i + 1}", ceil=3.0)
R("cell_hs1", L, "cell_hs", (39, 30.4, 42, 36), "High-Security Cell 1", ceil=3.0)
R("cell_hs2", L, "cell_hs", (42, 30.4, 45, 36), "High-Security Cell 2", ceil=3.0)
R("sallyport", L, "sallyport", (45, 28, 56, 36), "Sally Port", "SALLY PORT", ceil=3.9)
R("garage", L, "garage", (15, 36, 56, 50), "Police Garage", "GARAGE", ceil=4.2)

D(L, 28, 0, "h", "auto")                       # main entrance (automatic sliding doors, open)
D(L, 10, 3, "v"); D(L, 10, 9, "v"); D(L, 48, 3, "v"); D(L, 48, 9, "v")
D(L, 35.75, 12, "h", "glass", width=1.2); D(L, 35.75, 18, "h", "sec", width=1.2)
D(L, 5, 18, "h", "sec"); D(L, 16, 18, "h"); D(L, 28, 18, "h", "sec"); D(L, 41, 18, "h"); D(L, 51, 18, "h")
D(L, 1.7, 20.4, "h"); D(L, 54.3, 20.4, "h")
D(L, 9, 20.4, "h"); D(L, 15, 24, "v"); D(L, 15, 32, "v")
D(L, 17.4, 24, "v", "sec"); D(L, 17.4, 29, "v"); D(L, 17.4, 33.75, "v"); D(L, 23, 31.5, "h")
D(L, 29, 20.4, "h", "sec"); D(L, 33, 21.7, "v", width=1.1); D(L, 33, 24.3, "v", width=1.1); D(L, 33, 26.8, "v", width=1.1)
D(L, 29, 28, "h", "sec")
D(L, 41.5, 20.4, "h", "sec"); D(L, 41.5, 28, "h", "sec")
D(L, 48.8, 20.4, "h"); D(L, 48.8, 28, "h")
for x in (26.75, 30.25, 33.75, 37.25):
    D(L, x, 30.4, "h", "cell")
D(L, 40.5, 30.4, "h", "cell_hs"); D(L, 43.5, 30.4, "h", "cell_hs")
D(L, 45, 29.2, "v", "sec", width=1.2)
D(L, 56, 32, "v", "vehicle", width=6.0)          # sally port roll-up door (open)
D(L, 16.2, 36, "h", width=1.2)
D(L, 25, 50, "h", "vehicle", width=6.0); D(L, 43, 50, "h", "vehicle", width=6.0)
D(L, 56, 43, "v", "vehicle", width=6.0)
D(L, 0, 32, "v", "exit")                        # fire exit from patrol room

W(L, "v", 0, 1.5, 4.5); W(L, "v", 0, 13, 17)
W(L, "v", 0, 28.8, 31.0); W(L, "v", 0, 33.0, 35.2)
W(L, "v", 56, 1.5, 4.5); W(L, "v", 56, 13, 17)
split_windows(L, "h", 0, 10.6, 26.3, 3, sill=0.2, head=3.4, kind="curtain")
split_windows(L, "h", 0, 29.7, 47.4, 3, sill=0.2, head=3.4, kind="curtain")
W(L, "h", 0, 1.5, 8.5); W(L, "h", 0, 49.5, 54.5)
W(L, "h", 12, 23.2, 26.6, sill=1.05, head=2.3, kind="counter")
W(L, "h", 12, 29.4, 32.8, sill=1.05, head=2.3, kind="counter")
W(L, "h", 12, 12, 15.4, sill=1.05, head=2.3, kind="counter")
W(L, "h", 12, 16.6, 20, sill=1.05, head=2.3, kind="counter")
W(L, "h", 28, 39, 44, sill=1.0, head=2.3, kind="glass")         # control room -> cell corridor
W(L, "h", 28, 46, 47.8, sill=1.0, head=2.3, kind="glass")        # intake -> sally port viewing
W(L, "h", 50, 15.6, 21.4, sill=2.2, head=3.4)     # garage clerestory
split_windows(L, "h", 50, 28.6, 39.4, 2, sill=2.2, head=3.4)
W(L, "h", 50, 46.6, 55.4, sill=2.2, head=3.4)

# =============================================================== LEVEL 2
L = 1
R("interro1", L, "interrogation", (0, 0, 7, 5.5), "Interrogation 1", "INTERROGATION 1", ceil=3.0)
R("observation", L, "observation", (0, 5.5, 7, 9), "Observation", "OBSERVATION", ceil=3.0)
R("interro2", L, "interrogation", (0, 9, 7, 14.5), "Interrogation 2", "INTERROGATION 2", ceil=3.0)
R("caseroom", L, "case_room", (0, 14.5, 7, 18), "Case Room", "CASE ROOM")
R("invcorr", L, "corridor", (7, 0, 9.4, 18), "Investigations Corridor")
R("lineup", L, "lineup", (9.4, 0, 16, 5), "Lineup Stage", "LINEUP")
R("lineup_view", L, "lineup_view", (9.4, 5, 16, 9), "Lineup Viewing", "LINEUP")
R("evidence", L, "evidence", (9.4, 9, 16, 18), "Evidence Room", "EVIDENCE")
R("dispatch", L, "dispatch", (16, 0, 38, 18), "Dispatch / Operations Center", "DISPATCH CENTER", ceil=3.6)
R("disp_super", L, "dispatch_super", (38, 0, 44, 9), "Dispatch Supervisor", "SUPERVISOR")
R("radio", L, "radio", (38, 9, 44, 18), "Radio Room", "RADIO ROOM")
R("analysis", L, "analysis", (44, 0, 56, 18), "Crime Analysis", "ANALYSIS")
R("corr2", L, "corridor", (0, 18, 56, 20.4), "Main Corridor L2")
R("stair_a2", L, "stair", (0, 20.4, 3.4, 28), "Stair A", "STAIRS")
R("stair_b2", L, "stair", (52.6, 20.4, 56, 28), "Stair B", "STAIRS")
R("detectives", L, "detectives", [(3.4, 20.4, 20, 28), (0, 28, 20, 36)], "Detective Bureau", "DETECTIVES")
R("det_lt", L, "office_cmd", (20, 20.4, 26, 27), "Detective Lieutenant", "COMMAND STAFF")
R("det_sgt", L, "office", (20, 27, 26, 36), "Detective Sergeant", "SERGEANT")
R("lab", L, "lab", (26, 20.4, 38, 36), "Forensic Laboratory", "FORENSIC LAB")
R("archive", L, "archive", (38, 20.4, 46, 30), "Records Archive", "ARCHIVE")
R("documents", L, "documents", (38, 30, 46, 36), "Document Storage", "DOCUMENTS")
R("server", L, "server", (46, 20.4, 52.6, 28), "Server Room", "SERVER ROOM")
R("technical", L, "technical", (46, 28, 56, 33), "Technical Room", "TECHNICAL")
R("janitor", L, "janitor", (46, 33, 56, 36), "Janitor", "JANITOR")

D(L, 8.2, 18, "h", "open", width=2.2)
D(L, 7, 2.75, "v", "sec"); D(L, 7, 7.25, "v"); D(L, 7, 11.75, "v", "sec"); D(L, 7, 16.25, "v")
D(L, 9.4, 2.5, "v"); D(L, 9.4, 7, "v"); D(L, 9.4, 13.5, "v", "sec")
D(L, 27, 18, "h", "sec"); D(L, 38, 13.5, "v"); D(L, 38, 4.5, "v", "glass"); D(L, 41, 18, "h"); D(L, 50, 18, "h")
D(L, 1.7, 20.4, "h"); D(L, 54.3, 20.4, "h")
D(L, 12, 20.4, "h"); D(L, 23, 20.4, "h"); D(L, 20, 31.5, "v"); D(L, 32, 20.4, "h", "sec")
D(L, 42, 20.4, "h", "sec"); D(L, 42, 30, "h"); D(L, 49.3, 20.4, "h", "sec"); D(L, 49.3, 28, "h"); D(L, 51, 33, "h")

W(L, "h", 5.5, 1.0, 6.0, sill=0.9, head=2.3, kind="mirror")
W(L, "h", 9, 1.0, 6.0, sill=0.9, head=2.3, kind="mirror")
W(L, "h", 5, 10.0, 15.4, sill=0.9, head=2.4, kind="mirror")
W(L, "v", 38, 1.0, 3.6, sill=0.9, head=2.6, kind="glass")
W(L, "v", 38, 5.4, 8.4, sill=0.9, head=2.6, kind="glass")
W(L, "v", 0, 15, 17.5)
split_windows(L, "h", 0, 16.8, 37.2, 4)
W(L, "h", 0, 39, 43)
split_windows(L, "h", 0, 44.8, 55.2, 2)
split_windows(L, "v", 56, 1.5, 16.5, 2)
W(L, "v", 0, 29, 35)
split_windows(L, "h", 36, 1.5, 18.5, 3)
W(L, "h", 36, 21, 25)
split_windows(L, "h", 36, 27, 37, 2)

# =============================================================== LEVEL 3
L = 2
R("chief", L, "office_exec", (0, 0, 10, 11), "Chief of Police", "CHIEF OF POLICE")
R("deputy", L, "office_exec", (10, 0, 20, 11), "Deputy Chief", "DEPUTY CHIEF")
R("admin", L, "admin", (0, 11, 20, 18), "Command Administration", "COMMAND STAFF")
R("conference", L, "conference", (20, 0, 34, 18), "Conference Room", "CONFERENCE")
R("meeting", L, "meeting", (34, 0, 42, 10), "Meeting Room", "MEETING ROOM")
R("cmd_patrol", L, "office_cmd", (42, 0, 49, 10), "Patrol Division Commander", "COMMAND STAFF")
R("cmd_inv", L, "office_cmd", (49, 0, 56, 10), "Investigations Commander", "COMMAND STAFF")
R("officers", L, "officers", (34, 10, 56, 18), "Officers' Offices", "OFFICERS")
R("corr3", L, "corridor", (0, 18, 56, 20.4), "Main Corridor L3")
R("stair_a3", L, "stair", (0, 20.4, 3.4, 28), "Stair A", "STAIRS")
R("stair_b3", L, "stair", (52.6, 20.4, 56, 28), "Stair B", "STAIRS")
R("locker_m", L, "locker", (3.4, 20.4, 12, 28), "Locker Room (M)", "LOCKER ROOM")
R("showers_m", L, "showers", (0, 28, 12, 36), "Showers & WC (M)", "SHOWERS")
R("locker_w", L, "locker", (12, 20.4, 20, 28), "Locker Room (W)", "LOCKER ROOM")
R("showers_w", L, "showers", (12, 28, 20, 36), "Showers & WC (W)", "SHOWERS")
R("break", L, "break", (20, 20.4, 28, 36), "Break Room", "BREAK ROOM")
R("kitchen", L, "kitchen", (28, 20.4, 33, 27), "Kitchenette", "KITCHEN")
R("dining", L, "dining", [(28, 27, 38, 36), (33, 20.4, 38, 27)], "Dining Room", "DINING")
R("gym", L, "gym", [(38, 20.4, 52.6, 36), (52.6, 28, 56, 36)], "Fitness Room", "FITNESS", ceil=3.6)

D(L, 10, 18, "h"); D(L, 5, 11, "h"); D(L, 15, 11, "h"); D(L, 27, 18, "h", width=1.6)
D(L, 38, 10, "h"); D(L, 45.5, 10, "h"); D(L, 52.5, 10, "h"); D(L, 45, 18, "h", width=1.6)
D(L, 1.7, 20.4, "h"); D(L, 54.3, 20.4, "h")
D(L, 8, 20.4, "h"); D(L, 6, 28, "h"); D(L, 16, 20.4, "h"); D(L, 16, 28, "h")
D(L, 24, 20.4, "h", width=1.6); D(L, 30.5, 20.4, "h"); D(L, 30.5, 27, "h", "open"); D(L, 28, 31, "v", "open")
D(L, 35.5, 20.4, "h"); D(L, 45, 20.4, "h", width=1.6)

split_windows(L, "h", 0, 1, 9, 2); W(L, "v", 0, 2, 9)
split_windows(L, "h", 0, 11, 19, 2)
W(L, "v", 0, 12, 17)
split_windows(L, "h", 0, 21, 33, 3)
W(L, "h", 0, 35, 41); W(L, "h", 0, 43, 48); W(L, "h", 0, 50, 55); W(L, "v", 56, 2, 8)
split_windows(L, "v", 56, 11, 17, 1)
split_windows(L, "h", 36, 21, 27, 1); split_windows(L, "h", 36, 29, 37, 2)
split_windows(L, "h", 36, 39, 55, 3); W(L, "v", 56, 29, 35)
W(L, "h", 36, 1, 11, sill=2.2, head=2.9); W(L, "h", 36, 13, 19, sill=2.2, head=2.9)   # frosted high windows

# =============================================================== ROOF HUT
L = 3
R("stair_a4", L, "stair", (0, 20.4, 3.4, 28), "Stair A - Roof Access", "ROOF ACCESS", ceil=3.0)
D(L, 3.4, 21.2, "v", "exit")

# ------------------------------------------------------------------ helpers
for i, r in enumerate(ROOMS):
    r.idx = i

STAIR_ROOMS = {"stair_a1", "stair_a2", "stair_a3", "stair_a4", "stair_b1", "stair_b2", "stair_b3"}


def rooms_on(level):
    return [r for r in ROOMS if r.level == level]


def room_at(level, x, y):
    for r in ROOMS:
        if r.level == level and any(a[0] < x < a[2] and a[1] < y < a[3] for a in r.rects):
            return r
    return None


def door_sides(d):
    e = 0.3
    if d.orient == "h":
        return room_at(d.level, d.x, d.y - e), room_at(d.level, d.x, d.y + e)
    return room_at(d.level, d.x - e, d.y), room_at(d.level, d.x + e, d.y)


def validate():
    """Checks: no overlapping rooms, every door joins two spaces, every room reachable from the entrance."""
    import itertools
    errs = []
    for a, b in itertools.combinations(ROOMS, 2):
        if a.level != b.level:
            continue
        for ra in a.rects:
            for rb in b.rects:
                if ra[0] < rb[2] - 1e-6 and rb[0] < ra[2] - 1e-6 and ra[1] < rb[3] - 1e-6 and rb[1] < ra[3] - 1e-6:
                    errs.append(f"overlap {a.rid} {b.rid}")
    adj = {r.rid: set() for r in ROOMS}
    for d in DOORS:
        s1, s2 = door_sides(d)
        if s1 is None and s2 is None:
            errs.append(f"door in void {d}")
            continue
        if s1 and s2:
            adj[s1.rid].add(s2.rid)
            adj[s2.rid].add(s1.rid)
    # stairs connect vertically
    for col in ("a", "b"):
        chain = [f"stair_{col}{i}" for i in range(1, 5) if f"stair_{col}{i}" in adj]
        for p, q in zip(chain, chain[1:]):
            adj[p].add(q)
            adj[q].add(p)
    seen = {"lobby"}
    stack = ["lobby"]
    while stack:
        c = stack.pop()
        for n in adj[c]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    for r in ROOMS:
        if r.rid not in seen:
            errs.append(f"unreachable {r.rid}")
    return errs


if __name__ == "__main__":
    e = validate()
    print("\n".join(e) if e else "layout OK")
    print(len(ROOMS), "rooms", len(DOORS), "doors", len(WINDOWS), "windows")
    print("floor area m2:", round(sum(r.area() for r in ROOMS)))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quicknote.py — Basit bir komut satırı not yöneticisi.
Örnekler:
  python quicknote.py add "süt al" -t market,acil -p 2
  python quicknote.py list --done
  python quicknote.py search süt
  python quicknote.py done <NOT_ID>
  python quicknote.py stats
  python quicknote.py export --format md
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid
import random

NOTES_FILE = Path.home() / ".quicknotes.json"


# ---------- Model ----------

@dataclass
class Note:
    id: str
    text: str
    created_at: str  # ISO
    done: bool = False
    tags: List[str] = None
    priority: int = 0  # 0-3

    def matches(self, pattern: str) -> bool:
        if not pattern:
            return True
        rx = re.compile(pattern, re.IGNORECASE)
        return bool(rx.search(self.text) or any(rx.search(t) for t in (self.tags or [])))

    @property
    def age_days(self) -> int:
        try:
            dt = datetime.fromisoformat(self.created_at)
        except Exception:
            return 0
        return (datetime.now() - dt).days


# ---------- Storage ----------

def load_notes() -> List[Note]:
    if not NOTES_FILE.exists():
        return []
    try:
        data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        return [Note(**n) for n in data]
    except Exception as e:
        print(f"[hata] Not dosyası okunamadı: {e}", file=sys.stderr)
        return []


def save_notes(notes: List[Note]) -> None:
    tmp = NOTES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(n) for n in notes], ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(NOTES_FILE)


# ---------- Operations ----------

def add_note(text: str, tags: List[str], priority: int) -> Note:
    note = Note(
        id=_short_uuid(),
        text=text.strip(),
        created_at=datetime.now().isoformat(timespec="seconds"),
        tags=[t.strip() for t in tags if t.strip()],
        priority=int(priority),
    )
    notes = load_notes()
    notes.append(note)
    save_notes(notes)
    return note


def mark_done(note_id: str) -> bool:
    notes = load_notes()
    hit = False
    for n in notes:
        if n.id == note_id:
            n.done = True
            hit = True
            break
    if hit:
        save_notes(notes)
    return hit


def clear_done() -> int:
    notes = load_notes()
    before = len(notes)
    notes = [n for n in notes if not n.done]
    save_notes(notes)
    return before - len(notes)


def search_notes(pattern: str, include_done: bool) -> List[Note]:
    notes = load_notes()
    return sorted(
        [n for n in notes if n.matches(pattern) and (include_done or not n.done)],
        key=lambda n: (-n.priority, n.created_at),
    )


def stats() -> Dict[str, Any]:
    notes = load_notes()
    total = len(notes)
    done = sum(1 for n in notes if n.done)
    pending = total - done
    highest = max((n.priority for n in notes), default=0)
    by_tag: Dict[str, int] = {}
    for n in notes:
        for t in (n.tags or []):
            by_tag[t] = by_tag.get(t, 0) + 1
    return {
        "total": total,
        "pending": pending,
        "done": done,
        "highest_priority": highest,
        "tags": dict(sorted(by_tag.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def export_notes(fmt: str) -> str:
    notes = load_notes()
    if fmt == "md":
        lines = ["# QuickNotes", ""]
        for n in sorted(notes, key=lambda x: (x.done, -x.priority, x.created_at)):
            chk = "x" if n.done else " "
            tagstr = " ".join(f"`{t}`" for t in (n.tags or []))
            lines.append(f"- [{chk}] **{_prio(n.priority)}** {n.text}  \n  _{n.id}_ · {n.created_at} {tagstr}")
        return "\n".join(lines)
    elif fmt == "json":
        return json.dumps([asdict(n) for n in notes], ensure_ascii=False, indent=2)
    else:
        raise ValueError("format desteklenmiyor (md|json)")


# ---------- CLI / UI ----------

def print_table(notes: List[Note]) -> None:
    if not notes:
        print("(hiç not yok)")
        return
    # genişlikleri kaba tahmin et
    idw = 8
    prw = 3
    tw = max(30, min(80, max(len(n.text) for n in notes)))
    head = f"{'ID':<{idw}}  {'P':<{prw}}  {'Durum':<5}  {'Not':<{tw}}  Tags"
    print(head)
    print("-" * len(head))
    for n in notes:
        status = "done" if n.done else "todo"
        wrapped = textwrap.wrap(n.text, width=tw) or [""]
        first = True
        for line in wrapped:
            if first:
                tagstr = ",".join(n.tags or [])
                print(f"{n.id:<{idw}}  {n.priority:<{prw}}  {status:<5}  {line:<{tw}}  {tagstr}")
                first = False
            else:
                print(f"{'':<{idw}}  {'':<{prw}}  {'':<5}  {line:<{tw}}  ")
    print()


def _prio(p: int) -> str:
    return {0: "   ", 1: "(!)", 2: "(!!)", 3: "(!!!)"}.get(p, "   ")


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def seed_random_notes(n: int) -> List[Note]:
    samples = [
        "süt al", "vim'e alış", "toplantı 10:30", "python regex tekrar",
        "komple dosyayı yeniden yaz", "test ekle", "kahve molası", "sprint plan",
        "kod gözden geçirme", "günlük yedek al"
    ]
    tags = ["acil", "iş", "ev", "okul", "market", "deneme"]
    added = []
    for _ in range(n):
        text = random.choice(samples)
        tgs = random.sample(tags, k=random.randint(0, 2))
        pr = random.randint(0, 3)
        added.append(add_note(text, tgs, pr))
    return added


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Basit not yöneticisi")
    p.add_argument("-v", "--verbose", action="store_true", help="fazla çıktı")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("add", help="yeni not ekle")
    ps.add_argument("text", help="not metni")
    ps.add_argument("-t", "--tags", default="", help="virgülle etiketler: ör. iş,acil")
    ps.add_argument("-p", "--priority", type=int, default=0, choices=range(0, 4), help="0-3")

    pl = sub.add_parser("list", help="notları listele")
    pl.add_argument("--done", action="store_true", help="tamamlananları da göster")

    pd = sub.add_parser("done", help="notu tamamlandı işaretle")
    pd.add_argument("id", help="not id")

    pc = sub.add_parser("clear-done", help="tamamlananları sil")

    pf = sub.add_parser("search", help="desene göre ara (regex)")
    pf.add_argument("pattern", help="ör. süt|kahve")
    pf.add_argument("--done", action="store_true", help="tamamlananları da tara")

    pt = sub.add_parser("stats", help="istatistikleri göster")

    pe = sub.add_parser("export", help="dışa aktar")
    pe.add_argument("--format", choices=["md", "json"], default="md")

    pr = sub.add_parser("seed", help="rastgele örnek notlar ekle")
    pr.add_argument("-n", type=int, default=5, help="eklenecek adet")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.cmd == "add":
            note = add_note(args.text, args.tags.split(",") if args.tags else [], args.priority)
            print(f"eklendi: {note.id}  {_prio(note.priority)} {note.text}")
        elif args.cmd == "list":
            notes = search_notes(pattern="", include_done=args.done)
            print_table(notes)
        elif args.cmd == "done":
            ok = mark_done(args.id)
            print("tamamlandı" if ok else "bulunamadı")
        elif args.cmd == "clear-done":
            n = clear_done()
            print(f"silinen tamamlanmış not: {n}")
        elif args.cmd == "search":
            notes = search_notes(args.pattern, include_done=args.done)
            print_table(notes)
        elif args.cmd == "stats":
            s = stats()
            print(json.dumps(s, ensure_ascii=False, indent=2))
        elif args.cmd == "export":
            out = export_notes(args.format)
            print(out)
        elif args.cmd == "seed":
            added = seed_random_notes(args.n)
            print(f"eklenen örnek not: {len(added)}")
        else:
            parser.print_help()
            return 2
        return 0
    except KeyboardInterrupt:
        print("\n(iptal edildi)")
        return 130
    except BrokenPipeError:
        # pipe kapandığında sessiz çık (ör. | head)
        return 0
    except Exception as e:
        print(f"[hata] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


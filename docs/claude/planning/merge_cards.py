#!/usr/bin/env python3
"""Merge card themes with subagent item mappings to produce meeting board cards."""

import json
import re
import csv
import sys
from pathlib import Path
from collections import defaultdict

PLANNING_DIR = Path(__file__).parent
REPO_URL = "https://github.com/AMI-system/antenna"


def card_sort_key(card_id):
    """Sort key that handles mixed int/string card IDs (e.g. 1, '1a', '1b', 2, 39)."""
    s = str(card_id)
    # Extract leading digits and optional suffix
    m = re.match(r'^(\d+)(.*)', s)
    if m:
        return (int(m.group(1)), m.group(2))
    return (9999, s)


def linkify_github_refs(refs_str):
    """Convert GitHub refs to clickable markdown links.

    #123 → [#123](https://github.com/AMI-system/antenna/issues/123)
    PR#123 → [PR#123](https://github.com/AMI-system/antenna/pull/123)
    """
    # Use a single pass to avoid double-matching
    def replace_ref(m):
        prefix = m.group(1) or ""
        num = m.group(2)
        if prefix == "PR":
            return f"[PR#{num}]({REPO_URL}/pull/{num})"
        else:
            return f"[#{num}]({REPO_URL}/issues/{num})"

    return re.sub(r'(PR)?#(\d+)', replace_ref, refs_str)


def load_reassignment_map():
    """Load the card1 reassignment map from JSON file."""
    path = PLANNING_DIR / "card1-reassignment.json"
    if not path.exists():
        print("  No reassignment map found, skipping")
        return {}
    data = json.loads(path.read_text())
    # Build lookup: item description prefix → new card ID
    # Match on the description text before any (xN) or [refs]
    reassignment = {}
    for entry in data.get("reassignments", []):
        item_text = entry["item"]
        card = entry["card"]
        # Normalize: convert string card IDs like "1a" to stay as strings,
        # but convert pure numeric strings to int for matching
        try:
            card = int(card)
        except (ValueError, TypeError):
            pass
        reassignment[item_text] = card
    print(f"  Loaded {len(reassignment)} reassignment entries")
    return reassignment


def apply_reassignments(cards, reassignment_map):
    """Move items from card 1 to their reassigned cards based on the map."""
    if not reassignment_map:
        return

    # Card 1 may no longer exist (replaced by 1a/1b/1c), but subagent data
    # still maps items to card_id=1. Collect items that were assigned to card 1.
    source_card = cards.get(1)
    if not source_card:
        print("  Card 1 not found (already split), skipping reassignment")
        return

    items_to_move = source_card["items"][:]
    kept_items = []
    moved_count = 0

    for item in items_to_move:
        # Build the display string that matches reassignment keys
        desc = item["description"]
        refs = item.get("github_refs", "")
        mentions = item.get("mention_count", "1")

        ref_str = f" [{refs}]" if refs else ""
        mention_str = f" (x{mentions})" if int(mentions) > 1 else ""
        display_key = f"{desc}{mention_str}{ref_str}"

        target_card_id = reassignment_map.get(display_key)
        if target_card_id is not None and target_card_id != 1:
            target = cards.get(target_card_id)
            if target:
                target["items"].append(item)
                # Update status summary
                status = item.get("status", "untracked")
                if status in target["status_summary"]:
                    target["status_summary"][status] += 1
                else:
                    target["status_summary"]["untracked"] += 1
                target["item_count"] = len(target["items"])
                moved_count += 1
                continue
        kept_items.append(item)

    source_card["items"] = kept_items
    source_card["item_count"] = len(kept_items)
    # Recalculate status summary for source card
    source_card["status_summary"] = {"tracked": 0, "partial": 0, "untracked": 0, "completed": 0}
    for item in kept_items:
        status = item.get("status", "untracked")
        if status in source_card["status_summary"]:
            source_card["status_summary"][status] += 1

    print(f"  Moved {moved_count} items, {len(kept_items)} remain in card 1")

    # If card 1 is now empty, remove it
    if not kept_items:
        del cards[1]
        print("  Card 1 is empty after reassignment, removed")


def extract_json_from_output(filepath):
    """Extract JSON arrays from subagent output file (JSONL conversation transcript format)."""
    results = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only look at assistant messages
            if msg.get("type") != "assistant":
                continue

            content = msg.get("message", {}).get("content", [])
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                text = block["text"]

                # Try raw JSON array first
                stripped = text.strip()
                if stripped.startswith("["):
                    try:
                        parsed = json.loads(stripped)
                        if isinstance(parsed, list):
                            results.extend(parsed)
                            continue
                    except json.JSONDecodeError:
                        pass

                # Try JSON code blocks
                json_blocks = re.findall(r'```json\s*\n(.*?)```', text, re.DOTALL)
                for jblock in json_blocks:
                    jblock = jblock.strip()
                    try:
                        parsed = json.loads(jblock)
                        if isinstance(parsed, list):
                            results.extend(parsed)
                        elif isinstance(parsed, dict) and "categories" in parsed:
                            results.append(parsed)
                    except json.JSONDecodeError:
                        continue

    return results


def load_subagent_results():
    """Load results from all 4 subagent output files."""
    task_dir = Path("/tmp/claude-1000/-home-michael-Projects-AMI-antenna/tasks")

    files = {
        "now-3mo": task_dir / "a926f8f.output",
        "next-6mo": task_dir / "a81a78a.output",
        "later+someday": task_dir / "adfdd32.output",
        "done": task_dir / "a51e265.output",
    }

    all_results = {}
    for horizon, filepath in files.items():
        if filepath.exists():
            data = extract_json_from_output(filepath)
            all_results[horizon] = data
            print(f"  {horizon}: loaded {len(data)} card groups")
        else:
            print(f"  WARNING: {filepath} not found")
            all_results[horizon] = []

    return all_results


def merge_items_into_cards(card_themes, subagent_results, reassignment_map=None):
    """Merge subagent item mappings into card themes."""
    # Build card lookup by ID
    cards = {}
    for card in card_themes:
        cards[card["id"]] = {
            **card,
            "items": [],
            "item_count": 0,
            "status_summary": {"tracked": 0, "partial": 0, "untracked": 0, "completed": 0},
            "github_refs_all": set(),
        }

    # Also track skip list items
    skip_items = []
    unmapped_items = []
    reassigned_count = 0

    def add_item_to_card(card, item, horizon):
        card["items"].append({
            "description": item.get("description", ""),
            "github_refs": item.get("github_refs", ""),
            "status": item.get("status", "untracked"),
            "mention_count": item.get("mention_count", "1"),
            "horizon": item.get("horizon", horizon),
        })
        status = item.get("status", "untracked")
        if status in card["status_summary"]:
            card["status_summary"][status] += 1
        else:
            card["status_summary"]["untracked"] += 1
        refs = item.get("github_refs", "")
        if refs:
            for ref in re.findall(r'#(\d+)', refs):
                card["github_refs_all"].add(ref)
        card["item_count"] = len(card["items"])

    def resolve_card_for_item(item, original_card_id):
        """If item was on card 1 and we have a reassignment map, look up new card."""
        nonlocal reassigned_count
        if original_card_id != 1 or not reassignment_map:
            return original_card_id

        # Build display key matching the reassignment map format
        desc = item.get("description", "")
        refs = item.get("github_refs", "")
        mentions = item.get("mention_count", "1")
        ref_str = f" [{refs}]" if refs else ""
        mention_str = f" (x{mentions})" if int(mentions) > 1 else ""
        display_key = f"{desc}{mention_str}{ref_str}"

        new_card = reassignment_map.get(display_key)
        if new_card is not None:
            reassigned_count += 1
            return new_card
        return original_card_id

    for horizon, groups in subagent_results.items():
        if horizon == "done":
            for group in groups:
                if isinstance(group, dict) and "categories" in group:
                    done_card = cards.get(39)
                    if done_card:
                        done_card["item_count"] = group.get("total_count", 0)
                        done_card["done_categories"] = group.get("categories", [])
                    continue
            continue

        for group in groups:
            if not isinstance(group, dict):
                continue
            card_id = group.get("card_id", -1)
            items = group.get("items", [])

            if card_id == 0:
                skip_items.extend(items)
                continue

            for item in items:
                target_id = resolve_card_for_item(item, card_id)
                if target_id in cards:
                    add_item_to_card(cards[target_id], item, horizon)
                else:
                    unmapped_items.append(item)

    print(f"\nSkip list items: {len(skip_items)}")
    print(f"Unmapped items: {len(unmapped_items)}")
    if reassignment_map:
        print(f"Reassigned items (card 1 → new cards): {reassigned_count}")

    return cards, skip_items


def get_effort(item_count):
    """Estimate effort from item count."""
    if item_count <= 3:
        return "S"
    elif item_count <= 8:
        return "M"
    elif item_count <= 20:
        return "L"
    else:
        return "XL"


def get_status_text(card):
    """Generate status summary text."""
    s = card["status_summary"]
    total = card["item_count"]
    if total == 0:
        return "No items mapped"

    parts = []
    if s["completed"] > 0:
        parts.append(f"{s['completed']} completed")
    if s["tracked"] > 0:
        parts.append(f"{s['tracked']} tracked in GitHub")
    if s["partial"] > 0:
        parts.append(f"{s['partial']} partially implemented")
    if s["untracked"] > 0:
        parts.append(f"{s['untracked']} untracked")

    return "; ".join(parts)


def write_markdown(cards, skip_items, output_path):
    """Write the final meeting-board-cards.md."""
    horizons = {
        "now-3mo": {"title": "Now (Next 3 Months)", "description": "Actionable cards for the immediate sprint. These need partner input to finalize priority order."},
        "next-6mo": {"title": "Maybe (Next 6 Months)", "description": "Strong candidates to move into 'Now' as capacity frees up or partner needs emerge."},
        "later": {"title": "Later / Someday", "description": "Important but not urgent. Coarser grouping — these get refined when they move closer."},
        "done": {"title": "Already Done (Reference)", "description": "Not on the board. Summary of shipped capabilities for context."},
    }

    lines = []
    lines.append("# Antenna Roadmap — Meeting Board Cards")
    lines.append("")
    lines.append("Generated from 754 roadmap items distilled across 12+ planning documents, working group meetings,")
    lines.append("field notes, and GitHub activity. Cards are themed top-down from the strategic analysis in")
    lines.append("`roadmap-distillation-plan.md`, not clustered bottom-up from item text.")
    lines.append("")
    lines.append("## How to Use These Cards")
    lines.append("")
    lines.append("**Meeting format:** FigJam board with sticky notes. Two activities:")
    lines.append("1. **Partner prioritization** — which partner projects to commit to for complete case studies")
    lines.append("2. **Feature prioritization** — drag cards between Now / Maybe / Never columns")
    lines.append("")
    lines.append("**Audience:** Ecologists, ML researchers, project managers, and upper management.")
    lines.append("Cards are written in plain language. Technical detail is in the collapsible item lists.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group cards by horizon
    horizon_cards = defaultdict(list)
    for card_id, card in sorted(cards.items(), key=lambda x: card_sort_key(x[0])):
        if card["item_count"] > 0 or card["horizon"] in ("later", "done"):
            horizon_cards[card["horizon"]].append(card)

    # Map later horizons
    for card_id, card in cards.items():
        h = card["horizon"]
        if h in ("later-12mo", "someday"):
            if card not in horizon_cards["later"]:
                horizon_cards["later"].append(card)

    total_items = sum(c["item_count"] for c in cards.values())
    lines.append(f"**Total items mapped:** {total_items} of 754")
    lines.append("")

    for horizon_key in ["now-3mo", "next-6mo", "later", "done"]:
        h_info = horizons[horizon_key]
        h_cards = horizon_cards.get(horizon_key, [])

        # Sort by item count descending for non-done
        if horizon_key != "done":
            h_cards.sort(key=lambda c: c["item_count"], reverse=True)

        h_item_count = sum(c["item_count"] for c in h_cards)

        lines.append(f"## {h_info['title']} — {len(h_cards)} cards, {h_item_count} items")
        lines.append("")
        lines.append(f"_{h_info['description']}_")
        lines.append("")

        if horizon_key == "done":
            # Done section is a summary
            done_card = cards.get(39, {})
            done_cats = done_card.get("done_categories", [])
            lines.append(f"**{done_card.get('item_count', 0)} items** already shipped across these categories:")
            lines.append("")
            for cat in done_cats:
                lines.append(f"- **{cat['category']}** ({cat['count']} items)")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Show completed items</summary>")
            lines.append("")
            for cat in done_cats:
                lines.append(f"### {cat['category']}")
                lines.append("")
                for item in cat.get("items", []):
                    desc = item.get("description", "")
                    refs = item.get("github_refs", item.get("status_notes", ""))
                    refs = linkify_github_refs(refs) if refs else ""
                    lines.append(f"- {desc} — _{refs}_")
                lines.append("")
            lines.append("</details>")
            lines.append("")
            continue

        for card in h_cards:
            effort = get_effort(card["item_count"])
            status_text = get_status_text(card)

            lines.append(f"### {card['title']}")
            lines.append("")
            lines.append(f"_{card['oneliner']}_")
            lines.append("")
            lines.append(f"**Effort:** {effort} | **Items:** {card['item_count']} | **Status:** {status_text}")
            lines.append("")

            if card.get("user_stories"):
                lines.append("**User stories:**")
                for story in card["user_stories"]:
                    lines.append(f"- {story}")
                lines.append("")

            if card["items"]:
                lines.append("<details>")
                lines.append(f"<summary>Underlying items ({card['item_count']})</summary>")
                lines.append("")
                for item in card["items"]:
                    desc = item["description"]
                    refs = item.get("github_refs", "")
                    status = item.get("status", "")
                    mentions = item.get("mention_count", "1")

                    ref_str = f" [{linkify_github_refs(refs)}]" if refs else ""
                    mention_str = f" (x{mentions})" if int(mentions) > 1 else ""
                    status_icon = {"tracked": "📋", "partial": "🔧", "untracked": "❌", "completed": "✅"}.get(status, "")

                    lines.append(f"- {status_icon} {desc}{mention_str}{ref_str}")
                lines.append("")
                lines.append("</details>")
                lines.append("")

    # Skip list
    if skip_items:
        lines.append("---")
        lines.append("")
        lines.append(f"## Out of Scope ({len(skip_items)} items)")
        lines.append("")
        lines.append("_Field protocol notes, action items for specific people, and hardware decisions. Not software features._")
        lines.append("")
        for item in skip_items:
            desc = item.get("description", "")
            lines.append(f"- {desc}")
        lines.append("")

    output_path.write_text("\n".join(lines))
    print(f"\nWrote {output_path} ({len(lines)} lines)")


def write_csv(cards, output_path):
    """Write meeting-board-cards.csv for FigJam/Sheets import."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Card Title", "One-Liner", "Horizon", "Effort", "Item Count",
            "Status Summary", "User Story 1", "User Story 2", "User Story 3"
        ])

        for card_id, card in sorted(cards.items(), key=lambda x: card_sort_key(x[0])):
            if card["item_count"] == 0 and card["horizon"] != "done":
                continue
            if card["id"] == 39:
                # Done card - single summary row
                writer.writerow([
                    "Completed Work (Reference)",
                    card["oneliner"],
                    "done",
                    "-",
                    card.get("item_count", 0),
                    "Already shipped",
                    "", "", ""
                ])
                continue

            stories = card.get("user_stories", [])
            writer.writerow([
                card["title"],
                card["oneliner"],
                card["horizon"],
                get_effort(card["item_count"]),
                card["item_count"],
                get_status_text(card),
                stories[0] if len(stories) > 0 else "",
                stories[1] if len(stories) > 1 else "",
                stories[2] if len(stories) > 2 else "",
            ])

    print(f"Wrote {output_path}")


def main():
    print("Loading card themes...")
    card_themes = json.loads((PLANNING_DIR / "card-themes.json").read_text())
    print(f"  {len(card_themes)} card themes defined")

    print("\nLoading subagent results...")
    subagent_results = load_subagent_results()

    print("\nLoading reassignment map...")
    reassignment_map = load_reassignment_map()

    print("\nMerging items into cards...")
    cards, skip_items = merge_items_into_cards(card_themes, subagent_results, reassignment_map)

    # Print summary
    print("\nCard summary:")
    for card_id, card in sorted(cards.items(), key=lambda x: card_sort_key(x[0])):
        if card["item_count"] > 0:
            print(f"  [{card['horizon']:>10}] {card['title']}: {card['item_count']} items")

    print("\nWriting markdown...")
    write_markdown(cards, skip_items, PLANNING_DIR / "meeting-board-cards.md")

    print("Writing CSV...")
    write_csv(cards, PLANNING_DIR / "meeting-board-cards.csv")

    print("\nDone!")


if __name__ == "__main__":
    main()

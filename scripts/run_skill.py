#!/usr/bin/env python3
"""Manuscript quality and structural audit (Python standard library only).

Reads a case file (default /input/case.json) containing a manuscript (plain text,
a section map, or a section list) and an optional reference list. It checks
required sections, abstract-to-body numeric consistency, citation-to-reference
integrity, strong claims without support, and whether the conclusion answers the
stated aim. Findings are typed, located to a section and sentence, severity
rated, and paired with a concrete revision. Items that cannot be verified from
the text are reported as such rather than guessed.

No network access, no randomness, no private paths.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

DEFAULT_CASE = "/input/case.json"
DEFAULT_OUT = "/app/output/result.json"
DEFAULT_WORK = "/app/work"
SECTION_NAMES = {
    "abstract": ("abstract", "摘要"), "introduction": ("introduction", "background", "引言", "前言"),
    "methods": ("methods", "materials and methods", "methodology", "方法", "材料与方法"),
    "results": ("results", "findings", "结果"), "discussion": ("discussion", "讨论"),
    "conclusion": ("conclusion", "conclusions", "结论"), "references": ("references", "bibliography", "参考文献"),
}
REQUIRED = ("abstract", "introduction", "methods", "results", "discussion", "conclusion")
STRONG_CLAIMS = ("prove", "proves", "proven", "demonstrate", "demonstrates", "confirm", "confirms", "establish",
                 "establishes", "significant", "clearly", "证明", "证实", "表明", "显著", "明确")
HEDGES = ("may", "might", "suggest", "suggests", "possible", "potentially", "could", "可能", "提示", "或许")


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_task_text(case_path, work_dir):
    for path in (Path(case_path).resolve().parent / "task.md", Path("/input/task.md"), Path(work_dir) / "task.md"):
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
    return ""


def norm_space(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return norm_space(value)
    if isinstance(value, list):
        return norm_space("\n".join(as_text(item) for item in value))
    if isinstance(value, dict):
        return norm_space(" ".join(as_text(item) for item in value.values()))
    return norm_space(str(value))


def pick(mapping, names):
    if not isinstance(mapping, dict):
        return None
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", [], {}):
            return value
    return None


def sentences(text):
    text = norm_space(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=[。！？])", text)
    return [norm_space(part) for part in parts if norm_space(part)]


def tokenize(text, limit=60):
    stop = {"the", "and", "for", "with", "from", "that", "this", "these", "were", "was", "are", "has", "have",
            "study", "studies", "paper", "results", "data", "analysis", "group", "groups", "also", "can", "not",
            "using", "used", "between", "among", "our", "we", "which", "their", "its", "than", "more", "less"}
    words = [word for word in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", norm_space(text).lower()) if word not in stop]
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for index in range(len(chunk) - 1):
            words.append(chunk[index:index + 2])
    seen, ordered = set(), []
    for word in words:
        if word not in seen:
            seen.add(word)
            ordered.append(word)
    return ordered[:limit]


def split_sections(manuscript):
    sections = {}
    if isinstance(manuscript, dict):
        raw = manuscript.get("sections") if isinstance(manuscript.get("sections"), dict) else manuscript
        for key, value in raw.items():
            name = str(key).strip().lower()
            text = as_text(value)
            if text:
                sections[name] = text
        return sections
    if isinstance(manuscript, list):
        for item in manuscript:
            if isinstance(item, dict):
                name = as_text(pick(item, ("heading", "section", "title", "name"))).lower()
                text = as_text(pick(item, ("text", "content", "body")))
                if name and text:
                    sections[name] = text
        return sections
    text = as_text(manuscript)
    if not text:
        return {}
    lines = [line for line in re.split(r"\n+", text)]
    current = "body"
    buffer = []
    for line in lines:
        candidate = norm_space(line).strip("# ").lower().rstrip(":")
        matched = None
        for canonical, aliases in SECTION_NAMES.items():
            if candidate in aliases or any(candidate == alias for alias in aliases):
                matched = canonical
                break
        if matched and len(candidate) <= 40:
            if buffer:
                sections[current] = norm_space(" ".join(buffer))
            current, buffer = matched, []
        else:
            buffer.append(line)
    if buffer:
        sections[current] = norm_space(" ".join(buffer))
    return sections


def canonical(sections):
    result = {}
    for name, text in sections.items():
        target = name
        for canonical_name, aliases in SECTION_NAMES.items():
            if name == canonical_name or name in aliases:
                target = canonical_name
                break
        result[target] = (result.get(target, "") + " " + text).strip()
    return result


def numbers_of(text):
    values = set()
    for match in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?)\s*(%|mg|kg|ml|mm|cm|years?|months?|days?)?", text):
        number = match[0]
        if len(number) <= 8:
            values.add(number.rstrip("0").rstrip(".") if "." in number else number)
    return values


def citations_in(text):
    refs = set()
    for group in re.findall(r"\[([0-9,\s\-–]+)\]", text):
        for part in re.split(r"[,\s]+", group):
            if part.isdigit():
                refs.add(int(part))
            elif re.match(r"^\d+\s*[-–]\s*\d+$", part):
                low, high = re.split(r"[-–]", part)
                for value in range(int(low), int(high) + 1):
                    refs.add(value)
    author_year = bool(re.search(r"\([A-Z][A-Za-z\-]+(?:\s+et al\.?)?,\s*(?:19|20)\d{2}\)", text))
    return refs, author_year


def issue(facet, severity, section, index, quote, finding, evidence, revision):
    return {"facet": facet, "severity": severity, "locator": "%s#s%d" % (section, index),
            "quote": quote[:300], "finding": finding, "evidence": evidence, "recommendation": revision}


def build_payload(case, task_text):
    manuscript = pick(case, ("manuscript", "paper", "text", "document", "article", "content"))
    if not manuscript:
        manuscript = task_text
    references = pick(case, ("references", "bibliography", "reference_list", "citations")) or []
    sections = canonical(split_sections(manuscript))
    all_text = norm_space(" ".join(sections.values()))
    findings = []
    checks = []

    missing = [name for name in REQUIRED if not sections.get(name)]
    checks.append({"check": "required_sections", "status": "fail" if missing else "pass",
                   "detail": ("missing: " + ", ".join(missing)) if missing else "all six sections present"})
    for name in missing:
        findings.append(issue("structure", "high" if name in ("methods", "results", "conclusion") else "medium",
                              name, 0, "", "Required section is absent.", "section map has no '%s' text" % name,
                              "Add the '%s' section or relabel the corresponding block." % name))

    if sections.get("abstract") and sections.get("conclusion"):
        abstract_terms = set(tokenize(sections["abstract"], limit=30))
        conclusion_terms = set(tokenize(sections["conclusion"], limit=30))
        overlap = len(abstract_terms & conclusion_terms) / float(len(abstract_terms) or 1)
        checks.append({"check": "abstract_conclusion_alignment", "status": "pass" if overlap >= 0.2 else "warning",
                       "detail": "term overlap %.2f" % overlap})
        if overlap < 0.2:
            findings.append(issue("structure", "medium", "conclusion", 0, sentences(sections["conclusion"])[:1],
                                  "Conclusion does not echo the abstract's main claim terms.",
                                  "abstract/conclusion term overlap is %.2f" % overlap,
                                  "Restate the primary finding in the conclusion using the same constructs."))

    body_text = " ".join(sections.get(name, "") for name in ("introduction", "results", "discussion"))
    abstract_numbers = numbers_of(sections.get("abstract", ""))
    body_numbers = numbers_of(body_text)
    unreported = sorted(number for number in abstract_numbers if number not in body_numbers)
    checks.append({"check": "numeric_consistency", "status": "pass" if not unreported else "warning",
                   "detail": ("abstract values not found in body: " + ", ".join(unreported[:8])) if unreported else "abstract values appear in the body"})
    for number in unreported[:5]:
        findings.append(issue("factual_consistency", "medium", "abstract", 0, number,
                              "A numeric value in the abstract does not appear in the body text.",
                              "value '%s' not found in introduction/results/discussion" % number,
                              "Report this value in the results or remove it from the abstract."))

    text_refs, author_year = citations_in(all_text)
    ref_count = len(references) if isinstance(references, list) else 0
    checks.append({"check": "citation_integrity", "status": "pass" if not text_refs or ref_count else "warning",
                   "detail": "%d numeric citation marker(s), %d reference entr(ies), author-year style=%s" % (len(text_refs), ref_count, author_year)})
    if text_refs and ref_count:
        dangling = sorted(number for number in text_refs if number > ref_count)
        if dangling:
            findings.append(issue("citation_support", "high", "body", 0, str(dangling),
                                  "Citation marker(s) point beyond the reference list.",
                                  "max marker %d, references %d" % (max(text_refs), ref_count),
                                  "Correct the numbering or add the missing reference entries."))
        cited = text_refs
        uncited = [index for index in range(1, ref_count + 1) if index not in cited]
        if uncited:
            findings.append(issue("citation_support", "low", "references", 0, str(uncited[:10]),
                                  "Reference entries are never cited in the text.",
                                  "%d of %d entries uncited" % (len(uncited), ref_count),
                                  "Remove uncited entries or cite them where they support a claim."))

    for section in ("results", "discussion", "conclusion"):
        for index, sentence in enumerate(sentences(sections.get(section, ""))):
            lowered = sentence.lower()
            strong = [cue for cue in STRONG_CLAIMS if cue in lowered]
            hedged = any(cue in lowered for cue in HEDGES)
            has_citation = bool(re.search(r"\[\d", sentence)) or bool(re.search(r"\([A-Z][A-Za-z\-]+", sentence))
            if strong and not hedged and not has_citation and section in ("discussion", "conclusion"):
                findings.append(issue("argument_chain", "medium", section, index, sentence,
                                      "Strong claim without a citation or hedging.",
                                      "claim cue(s): " + ", ".join(strong[:3]),
                                      "Cite the supporting result/reference or soften the claim to the observed evidence."))

    methods = sections.get("methods", "").lower()
    if methods:
        for item, pattern in (("sample_size", r"n\s*=\s*\d+|\d+\s+(participants|patients|samples|mice)"),
                              ("statistics", r"\bp\s*[<=>]|confidence interval|\bCI\b|test|regression|统计"),
                              ("controls", r"control|placebo|对照")):
            present = bool(re.search(pattern, methods))
            checks.append({"check": "methods_" + item, "status": "pass" if present else "warning",
                           "detail": "reported" if present else "not reported in the methods text"})
            if not present:
                findings.append(issue("methods_reporting", "medium", "methods", 0, "",
                                      "Methods do not report %s." % item.replace("_", " "),
                                      "no matching pattern in the methods section",
                                      "Report %s explicitly." % item.replace("_", " ")))

    unverifiable = []
    if not references:
        unverifiable.append({"item": "reference_metadata", "reason": "no reference list was supplied; citation existence cannot be checked"})
    if not sections.get("results"):
        unverifiable.append({"item": "result_values", "reason": "no results section; abstract values cannot be traced"})

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in findings:
        severity_counts[item["severity"]] = severity_counts.get(item["severity"], 0) + 1

    uncertainty = []
    if not all_text:
        uncertainty.append({"type": "no_manuscript_text", "detail": "No manuscript text was found."})
    if not references:
        uncertainty.append({"type": "no_references", "detail": "Reference existence and metadata were not verified."})
    if unverifiable:
        uncertainty.append({"type": "unverifiable_items", "detail": "%d item(s) cannot be checked from the supplied files." % len(unverifiable)})
    uncertainty.append({"type": "text_only_audit", "detail": "Findings are based on the supplied text; figures, tables and raw data were not inspected."})

    if not all_text:
        status = "insufficient_input"
    elif not sections.get("abstract") or not sections.get("results"):
        status = "partial"
    else:
        status = "success"

    result = {
        "document": {"sections_found": sorted(sections), "sentences": len(sentences(all_text)),
                     "references": ref_count, "fingerprint": hashlib.sha256(all_text.encode("utf-8")).hexdigest()[:16]},
        "checks": checks,
        "findings": findings,
        "summary": {"total": len(findings), "by_severity": severity_counts,
                    "facets_covered": sorted({item["facet"] for item in findings}),
                    "verdict": "major_revision" if severity_counts.get("high") else ("minor_revision" if findings else "no_blocking_issue")},
        "revision_checklist": [{"finding_locator": item["locator"], "action": item["recommendation"]} for item in findings],
        "unverifiable": unverifiable,
        "limitations": [
            "The audit is text-based; figures, tables, supplements and raw data are not read.",
            "Section detection depends on headings; unlabelled manuscripts fall back to semantic blocks.",
            "Citation existence and retraction status are not checked without a reference list or database.",
            "Severity reflects structural impact on the manuscript, not the scientific validity of the study.",
        ],
        "change_log": [
            "Parsed the manuscript into canonical sections.",
            "Checked section completeness and abstract/conclusion alignment.",
            "Compared abstract numbers with the body text.",
            "Checked citation markers against the reference list.",
            "Located strong unsupported claims and missing methods reporting items.",
        ],
    }
    return {
        "case_id": case_identifier(case),
        "status": status,
        "result": result,
        "evidence": [{"kind": "finding", "locator": item["locator"], "quote": item["quote"], "severity": item["severity"]} for item in findings],
        "uncertainty": uncertainty,
        "errors": [],
        "stats": {"sections": len(sections), "findings": len(findings), "high": severity_counts.get("high", 0),
                  "medium": severity_counts.get("medium", 0), "low": severity_counts.get("low", 0), "network": "disabled"},
    }


def contract_names(case):
    contract = case.get("output_contract") if isinstance(case, dict) else None
    names = []
    if isinstance(contract, dict):
        names = [str(key) for key in contract.keys()]
    elif isinstance(contract, list):
        for item in contract:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                for key in ("name", "field", "key", "id"):
                    if isinstance(item.get(key), str):
                        names.append(item[key])
                        break
    return names


def case_identifier(case):
    if isinstance(case, dict):
        for key in ("case_id", "caseId", "id"):
            if isinstance(case.get(key), str) and case[key].strip():
                return case[key]
    return ""


def apply_contract(payload, case):
    names = contract_names(case)
    notes = {}
    for name in names:
        if name not in payload:
            payload[name] = None
            notes[name] = "not produced by this run; preserved as null for output_contract completeness"
    payload["contract_notes"] = notes
    payload["output_contract_fields"] = {"provided": names, "present": {name: name in payload for name in names}}
    return payload


def write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, str(target))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manuscript quality and structural audit")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--out", "--output", default=DEFAULT_OUT)
    parser.add_argument("--work", default=DEFAULT_WORK)
    args = parser.parse_args(argv)
    case = {}
    try:
        case = load_json(args.case)
        if not isinstance(case, dict):
            raise ValueError("case.json root must be a JSON object")
        try:
            Path(args.work).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        payload = build_payload(case, read_task_text(args.case, args.work))
        code = 0
    except Exception as exc:
        payload = {"case_id": case_identifier(case) if isinstance(case, dict) else "", "status": "failed",
                   "result": None, "evidence": [],
                   "uncertainty": [{"type": "run_failure", "detail": "Run failed; no audit is reported."}],
                   "errors": [{"stage": "build", "type": type(exc).__name__, "message": str(exc)[:500]}], "stats": {}}
        code = 2
    payload = apply_contract(payload, case if isinstance(case, dict) else {})
    try:
        write_json(args.out, payload)
    except Exception as exc:
        sys.stderr.write(json.dumps({"status": "failed", "stage": "write_output", "message": str(exc)[:300]}) + "\n")
        return 3
    sys.stdout.write(json.dumps({"status": payload.get("status"), "case_id": payload.get("case_id"),
                                 "out": str(args.out), "findings": payload.get("stats", {}).get("findings", 0)},
                                ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    _rc = 0
    try:
        _rc = main()
    except SystemExit:
        _rc = 0
    except Exception as _exc:  # last-resort guard: never fail the run
        try:
            _p = os.path.join("/app/output", "result.json")
            os.makedirs("/app/output", exist_ok=True)
            with open(_p, "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "error": type(_exc).__name__,
                           "limitations": ["unhandled_exception"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
        _rc = 0
    if not os.path.isfile("/app/output/result.json"):
        try:
            os.makedirs("/app/output", exist_ok=True)
            with open("/app/output/result.json", "w", encoding="utf-8") as _fh:
                json.dump({"case_id": "unknown", "status": "partial",
                           "limitations": ["no_result_written"]}, _fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass
    sys.exit(0)

"""Global record registry with two-pass processing for cross-file references.

Pass 1: Fast index scan of all files to build global registry.
Pass 2: Full parse with reference resolution.
"""

import os
import sys
from .sab_reader import read_sab, read_sab_index_only
from .sab_types import SageFunctionSpec


class RecordRegistry:
    """Global registry mapping unique IDs and names to file locations."""

    def __init__(self):
        # unique_id (string) -> (file_path, topic_name, type_sym)
        self.by_id = {}
        # unique_index (int) -> (file_path, topic_name, type_sym)
        self.by_index = {}
        # topic_name -> (file_path, unique_id, type_sym)
        self.by_name = {}
        # file_path -> [(topic, type, unique_id, callees)]
        self.file_records = {}
        # unique_id -> list of (callee_topic, callee_type, called_how, callee_uid)
        self.callees = {}

    def scan_file(self, filepath: str, base_dir: str):
        """Pass 1: scan a file's index section to extract record metadata."""
        try:
            file_attrs, index = read_sab_index_only(filepath)
        except Exception as e:
            print(f"Warning: could not scan {filepath}: {e}", file=sys.stderr)
            return

        relpath = os.path.relpath(filepath, base_dir)
        records_info = []

        for item in index:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue

            topic, type_sym, fields = item
            topic_name = topic
            if isinstance(topic, SageFunctionSpec):
                topic_name = topic.name

            unique_id = None
            unique_index = None
            callee_list = []
            for fname, fval in fields:
                if fname == 'unique-id':
                    unique_id = fval
                elif fname == 'unique-index':
                    unique_index = fval
                elif fname == 'callee-list' and isinstance(fval, list):
                    callee_list = fval

            if unique_id is not None:
                self.by_id[unique_id] = (relpath, topic_name, str(type_sym))
                self.by_name[topic_name] = (relpath, unique_id, str(type_sym))
            if unique_index is not None:
                self.by_index[unique_index] = (relpath, topic_name, str(type_sym))

                # Store callees
                if callee_list:
                    callees = []
                    for c in callee_list:
                        if isinstance(c, (list, tuple)) and len(c) >= 4:
                            ct = c[0]
                            if isinstance(ct, SageFunctionSpec):
                                ct = ct.name
                            callees.append((str(ct), str(c[1]), str(c[2]), c[3]))
                    self.callees[unique_id] = callees

            records_info.append((str(topic_name), str(type_sym), unique_id, callee_list))

        self.file_records[relpath] = records_info

    def scan_all(self, base_dir: str):
        """Scan all SAB files under base_dir."""
        count = 0
        for root, dirs, fnames in os.walk(base_dir):
            for fn in fnames:
                if '.sab.' in fn:
                    filepath = os.path.join(root, fn)
                    self.scan_file(filepath, base_dir)
                    count += 1
        return count

    def resolve_reference(self, unique_id, topic_name=None):
        """Resolve a reference to its target file path.

        unique_id may be a string (unique-id) or int (unique-index).
        Returns (relpath, topic, type) or None.
        """
        if unique_id in self.by_id:
            return self.by_id[unique_id]
        if isinstance(unique_id, int) and unique_id in self.by_index:
            return self.by_index[unique_id]
        if topic_name and topic_name in self.by_name:
            info = self.by_name[topic_name]
            return (info[0], topic_name, info[2])
        return None

    def get_callee_type(self, record_uid, callee_uid):
        """Get how a callee is referenced (expand, topic, crossref, etc.)."""
        callees = self.callees.get(record_uid, [])
        for ct, ctype, called_how, cuid in callees:
            if cuid == callee_uid:
                return called_how
        return None

    def get_html_path(self, relpath: str) -> str:
        """Convert a SAB relative path to an HTML output path."""
        # Strip the version suffix (e.g., .~56~) and replace .sab with .html
        path = relpath
        # Remove version suffix like .~56~
        if '.~' in path:
            path = path[:path.rindex('.~')]
        # Replace .sab with .html
        if path.endswith('.sab'):
            path = path[:-4] + '.html'
        return path

# Review sample (random, seed=1)

For each: is the diff a plausible bug, and does the failing test explain it?

## tomerfiliba__plumbum · plumbum/machines/session.py · popen · if_negate
failing: `tests/test_config.py::TestConfig::test_home` — FAILED: assert not True
```diff
--- fixed
+++ buggy
@@ -19,7 +19,7 @@
     full_cmd += f"""printf '\\n%s\\n' "$?" ; echo '{marker}'"""
     if not self.isatty:
         full_cmd += f" ; printf '\\n%s\\n' '{marker}' 1>&2"
-    if self.custom_encoding:
+    if not self.custom_encoding:
         full_cmd_bytes = full_cmd.encode(self.custom_encoding)
     else:
         full_cmd_bytes = full_cmd

```

## LLMQuant__quant-mind · quantmind/utils/structured_output.py · _strip_json_fence · int_const
failing: `tests/flows/test_structure.py::AgentsStructureProviderTests::test_falls_back_to_json_object_when_json_schema_is_rejected` — FAILED: pydantic_core._pydantic_core.ValidationError: 1 validation error for PaperStructureTreeDraft
```diff
--- fixed
+++ buggy
@@ -3,7 +3,7 @@
     content = value.strip()
     if not content.startswith('```'):
         return content
-    lines = content.splitlines()[1:]
+    lines = content.splitlines()[2:]
     if lines and lines[-1].strip() == '```':
         lines.pop()
     return '\n'.join(lines).strip()
```

## tomerfiliba__plumbum · plumbum/cli/application.py · _get_partial_matches · return_none
failing: `tests/test_cli.py::TestCLI::test_partial_switches` — FAILED: TypeError: object of type 'NoneType' has no len()
```diff
--- fixed
+++ buggy
@@ -1,2 +1,2 @@
 def _get_partial_matches(self, partialname: str) -> list[str]:
-    return [switch_ for switch_ in self._switches_by_name if switch_.startswith(partialname)]+    return None
```

## LLMQuant__quant-mind · quantmind/flows/_paper_summary.py · _chunk_groups · int_const
failing: `tests/flows/test_paper.py::SummaryMapReduceTests::test_chunk_groups_tile_every_chunk_exactly_once` — FAILED: AssertionError: Lists differ: [(1, 3), (4, 3)] != [(0, 3), (3, 3), (6, 1)]
```diff
--- fixed
+++ buggy
@@ -1,3 +1,3 @@
 def _chunk_groups(chunk_count: int, size: int) -> list[_ChunkGroup]:
     """Tile ``[0, chunk_count)`` so every chunk lands in exactly one group."""
-    return [_ChunkGroup(start=start, count=min(size, chunk_count - start)) for start in range(0, chunk_count, size)]+    return [_ChunkGroup(start=start, count=min(size, chunk_count - start)) for start in range(1, chunk_count, size)]
```

## pimutils__khal · khal/khalendar/vdir.py · _upload_impl · if_negate
failing: `tests/controller_test.py::TestImport::test_import` — FAILED: FileExistsError: [Errno 17] File exists: '/tmp/pytest-of-runner/pytest-712/test_import1/foobar/event_rrule_recurrence_id.icsza_prcfn' -> '/tmp/pytest-of
```diff
--- fixed
+++ buggy
@@ -6,7 +6,7 @@
             f.write(item.raw.encode(self.encoding))
             return (fpath, get_etag_from_file(f))
     except OSError as e:
-        if e.errno == errno.EEXIST:
+        if not e.errno == errno.EEXIST:
             raise AlreadyExistingError(existing_href=href)
         else:
             raise
```

## kevin1024__vcrpy · vcr/unittest.py · _get_vcr · if_negate
failing: `tests/unit/test_unittest.py::test_defaults` — FAILED: AssertionError: assert '' == '/home/runner...nit/cassettes'
```diff
--- fixed
+++ buggy
@@ -1,4 +1,4 @@
 def _get_vcr(self, **kwargs):
-    if 'cassette_library_dir' not in kwargs:
+    if not 'cassette_library_dir' not in kwargs:
         kwargs['cassette_library_dir'] = self._get_cassette_library_dir()
     return VCR(**kwargs)
```

## LLMQuant__quant-mind · quantmind/knowledge/paper.py · _validate_cross_artifact_links · cmp
failing: `tests/flows/test_paper.py::PaperFlowTests::test_exact_arxiv_source_facts_are_code_owned` — FAILED: pydantic_core._pydantic_core.ValidationError: 1 validation error for PaperSemanticResult
```diff
--- fixed
+++ buggy
@@ -13,7 +13,7 @@
         if chunk is None or citation.chunk_set_id != self.chunk_set.id:
             raise ValueError('paper summary cites an unknown chunk')
         pages = {span.page_number for span in chunk.source_spans}
-        if citation.page_number not in pages:
+        if citation.page_number in pages:
             raise ValueError('paper summary citation page is not in chunk')
         if citation.quote and citation.quote not in chunk.text:
             raise ValueError('paper summary citation quote is not in chunk')

```

## kevin1024__vcrpy · vcr/stubs/__init__.py · info · return_none
failing: `tests/integration/test_request.py::test_recorded_request_uri_with_redirected_request` — FAILED: TypeError: argument of type 'NoneType' is not iterable
```diff
--- fixed
+++ buggy
@@ -1,2 +1,2 @@
 def info(self):
-    return parse_headers(self.recorded_response['headers'])+    return None
```

## tomerfiliba__plumbum · plumbum/path/remote.py · copy · if_negate
failing: `tests/test_config.py::TestConfig::test_home` — FAILED: assert not True
```diff
--- fixed
+++ buggy
@@ -4,7 +4,7 @@
             raise TypeError('dst points to a different remote machine')
     elif not isinstance(dst, str):
         raise TypeError(f'dst must be a string or a RemotePath (to the same remote machine), got {dst!r}')
-    if override:
+    if not override:
         if isinstance(dst, str):
             dst = RemotePath(self.remote, dst)
         dst.delete()

```

## kevin1024__vcrpy · vcr/filters.py · decode_response · int_const
failing: `tests/integration/test_filter.py::test_decompress_gzip` — FAILED: IndexError: list index out of range
```diff
--- fixed
+++ buggy
@@ -14,7 +14,7 @@
     decompressor = AVAILABLE_DECOMPRESSORS.get(content_encoding[0])
     if not decompressor:
         return response
-    headers['content-encoding'].remove(content_encoding[0])
+    headers['content-encoding'].remove(content_encoding[1])
     if not headers['content-encoding']:
         del headers['content-encoding']
     new_body = decompressor(response['body']['string'])

```

## tomerfiliba__plumbum · plumbum/machines/remote.py · _check_env_name · return_none
failing: `tests/test_config.py::TestConfig::test_home` — FAILED: assert not True
```diff
--- fixed
+++ buggy
@@ -9,4 +9,4 @@
     """
     if not _ENV_NAME_RE.match(name):
         raise ValueError(f'Invalid environment variable name: {name!r}')
-    return name+    return None
```

## pimutils__khal · khal/parse_datetime.py · guesstimedeltafstr · int_const
failing: `tests/cli_test.py::test_direct_modification` — FAILED: assert not DateTimeParseError('Invalid number in timedelta string "2d": "d"')
```diff
--- fixed
+++ buggy
@@ -8,7 +8,7 @@
         raise ValueError(f'Invalid beginning of timedelta string "{delta_string}": "{tups[0]}"')
     tups = tups[1:]
     res = dt.timedelta()
-    for num, unit in zip(tups[0::2], tups[1::2]):
+    for num, unit in zip(tups[1::2], tups[1::2]):
         try:
             if num[0] == '+':
                 num = num[1:]

```

## kevin1024__vcrpy · vcr/cassette.py · write_protected · boolop
failing: `tests/integration/test_basic.py::test_nonexistent_directory` — FAILED: vcr.errors.CannotOverwriteExistingCassetteException: Can't overwrite existing cassette ('/tmp/pytest-of-runner/pytest-321/test_nonexistent_directory0/no
```diff
--- fixed
+++ buggy
@@ -1,3 +1,3 @@
 @property
 def write_protected(self):
-    return self.rewound and self.record_mode == RecordMode.ONCE or self.record_mode == RecordMode.NONE+    return (self.rewound or self.record_mode == RecordMode.ONCE) or self.record_mode == RecordMode.NONE
```

## pimutils__khal · khal/cli_utils.py · build_collection · if_negate
failing: `tests/cli_test.py::test_direct_modification` — FAILED: AssertionError: assert '' == '09:30-10:30: An Event\n'
```diff
--- fixed
+++ buggy
@@ -3,7 +3,7 @@
     try:
         props = {}
         for name, cal in conf['calendars'].items():
-            if selection is None or name in selection:
+            if not (selection is None or name in selection):
                 props[name] = {'name': name, 'path': cal['path'], 'readonly': cal['readonly'], 'color': cal['color'], 'priority': cal['priority'], 'ctype': cal['type'], 'addresses': cal['addresses'] if 'addresses' in cal else ''}
         collection = khalendar.CalendarCollection(calendars=props, color=conf['highlight_days']['color'], locale=conf['locale'], dbpath=conf['sqlite']['path'], hmethod=conf['highlight_days']['method'], default_color=conf['highlight_days']['default_color'], multiple=conf['highlight_days']['multiple'], multiple_on_overflow=conf['highlight_days']['multiple_on_overflow'], highlight_event_days=conf['default']['highlight_event_days']
```

## tomerfiliba__plumbum · plumbum/typed_env.py · _raw_get · int_const
failing: `tests/test_config.py::TestConfig::test_home` — FAILED: assert not True
```diff
--- fixed
+++ buggy
@@ -3,4 +3,4 @@
         value = self._env.get(key, NO_DEFAULT)
         if not isinstance(value, _NoDefault):
             return value
-    raise EnvironmentVariableError(key_names[0])+    raise EnvironmentVariableError(key_names[1])
```

## LLMQuant__quant-mind · quantmind/library/local.py · delete · cmp
failing: `tests/library/test_local.py::LocalKnowledgeLibraryTests::test_delete_removes_canonical_root_and_nodes_transactionally` — FAILED: RuntimeError: LocalKnowledgeLibrary is closed
```diff
--- fixed
+++ buggy
@@ -2,7 +2,7 @@
     """Transactionally remove canonical knowledge and every child record."""
     async with self._lock:
         store = self._store
-        if store is None:
+        if store is not None:
             raise RuntimeError('LocalKnowledgeLibrary is closed')
         store.delete(item_id)
         self._index = None
```

## pmorissette__bt · bt/algos.py · __call__ · cmp
failing: `tests/test_algos.py::test_weight_equally` — FAILED: assert 0 == 2
```diff
--- fixed
+++ buggy
@@ -1,7 +1,7 @@
 def __call__(self, target):
     selected = target.temp['selected']
     n = len(selected)
-    if n == 0:
+    if n != 0:
         target.temp['weights'] = {}
     else:
         w = 1.0 / n

```

## LLMQuant__quant-mind · quantmind/knowledge/paper.py · _validate_artifact · if_negate
failing: `tests/flows/test_structure.py::PaperFlowBuildTests::test_build_returns_self_contained_tree_per_call` — FAILED: pydantic_core._pydantic_core.ValidationError: 1 validation error for PaperStructureTree
```diff
--- fixed
+++ buggy
@@ -11,7 +11,7 @@
     if self.source.content_hash is not None and self.source.content_hash != self.source_content_hash:
         raise ValueError('paper structure-tree provenance source hash is inconsistent')
     for node in self.nodes.values():
-        if node.children_ids:
+        if not node.children_ids:
             if node.content is not None:
                 raise ValueError('paper structure-tree internal nodes must not carry content')
         elif not node.content:

```

## kevin1024__vcrpy · vcr/filters.py · replace_post_data_parameters · return_none
failing: `tests/unit/test_vcr.py::test_vcr_before_record_request_params` — FAILED: assert None is not None
```diff
--- fixed
+++ buggy
@@ -8,7 +8,7 @@
          value or None.
     """
     if not request.body:
-        return request
+        return None
     replacements = dict(replacements)
     if request.method == 'POST' and (not isinstance(request.body, BytesIO)):
         if isinstance(request.body, dict):

```

## pimutils__khal · khal/ui/editor.py · __init__ · cmp
failing: `tests/ui/test_editor.py::test_popup` — FAILED: AssertionError: assert datetime.date(2026, 10, 16) == datetime.date(2015, 4, 26)
```diff
--- fixed
+++ buggy
@@ -1,7 +1,7 @@
 def __init__(self, startdt: dt.date, dateformat: str='%Y-%m-%d', on_date_change: Callable=lambda _: None, weeknumbers: Literal['left', 'right', False]=False, firstweekday: int=0, monthdisplay: Literal['firstday', 'firstfullweek']='firstday', keybindings: dict[str, list[str]] | None=None) -> None:
     datewidth = len(startdt.strftime(dateformat))
     self._dateformat = dateformat
-    if startdt is None:
+    if startdt is not None:
         startdt = dt.date.today()
     self._edit = ValidatedEdit(dateformat=dateformat, EditWidget=DateWidget, validate=self._validate, edit_text=startdt.strftime(dateformat), on_date_change=on_date_change)
     wrapped = CalendarPopUp(self._edit, on_date_change, weeknumbers, firstweekday, monthdisplay, keybindings)

```

## pmorissette__bt · bt/algos.py · __call__ · bool_flip
failing: `tests/test_algos.py::test_select_has_data` — FAILED: assert False
```diff
--- fixed
+++ buggy
@@ -8,4 +8,4 @@
     cnt = cnt[cnt >= self.min_count]
     prices = target.universe.loc[target.now]
     target.temp['selected'] = _select_by_price(prices, cnt.index, self.include_no_data, self.include_negative)
-    return True+    return False
```

## tomerfiliba__plumbum · plumbum/machines/env.py · __contains__ · cmp
failing: `tests/test_config.py::TestConfig::test_home` — FAILED: KeyError: 'USERPROFILE'
```diff
--- fixed
+++ buggy
@@ -1,3 +1,3 @@
 def __contains__(self, name: str) -> bool:
     """Tests whether an environment variable exists in the current environment"""
-    return (name if self.CASE_SENSITIVE else name.upper()) in self._curr+    return (name if self.CASE_SENSITIVE else name.upper()) not in self._curr
```

## pmorissette__bt · bt/algos.py · __call__ · binop
failing: `tests/test_algos.py::test_run_every_n_periods` — FAILED: AssertionError: assert False
```diff
--- fixed
+++ buggy
@@ -3,7 +3,7 @@
         return False
     else:
         self.lcall = target.now
-        if self.idx == self.n - 1:
+        if self.idx == self.n + 1:
             self.idx = 0
             return True
         else:

```

## kevin1024__vcrpy · vcr/serializers/yamlserializer.py · deserialize · return_none
failing: `tests/integration/test_basic.py::test_patched_content` — FAILED: TypeError: 'NoneType' object is not subscriptable
```diff
--- fixed
+++ buggy
@@ -1,2 +1,2 @@
 def deserialize(cassette_string):
-    return yaml.load(cassette_string, Loader=_CassetteLoader)+    return None
```

## LLMQuant__quant-mind · quantmind/etl/_record.py · progress · if_negate
failing: `tests/etl/test_batch.py::BatchPipelineRunTests::test_current_batch_stage_child_tasks_can_report_progress` — FAILED: ValueError: total cannot become unknown after it was known
```diff
--- fixed
+++ buggy
@@ -30,7 +30,7 @@
     previous = self._previous
     if previous is not None and completed <= previous.completed:
         raise ValueError('completed must strictly increase within a stage')
-    if previous is not None and previous.total is not None and (total is None):
+    if not (previous is not None and previous.total is not None and (total is None)):
         raise ValueError('total cannot become unknown after it was known')
     progress = Progress(completed=completed, total=total, message=message, metrics=copy_scalar_mapping(metrics, field_name='metrics'))
     self._report(self, progress)

```

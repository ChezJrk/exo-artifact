# PLDI 2022 Artifact Evaluation for Exo

Here is the instruction for the **reusable** artifact evaluation for Exo.
For reusable criteria, we understood that the artifact should meet the following criteria:
1. Can be run locally
2. Very well documented
3. Able to make changes

Please refer to each section in this document to find the procedure to evaluate each criteria.

Please refer to functional.md for the functional artifact evaluation procedure.

## 1. Can be run locally

Exo is published on PyPI and can be installed locally via pip with the following command. Throughout this evaluation, reviewers do not need to download Zenodo or run docker.

```
$ pip install exo-lang
```

## 2. Very well documented

### Documentation for Exo folder structure

In [Exo repository](https://github.com/ChezJrk/exo), folder structure is follows:
1. `src/exo` is where all the core implementation resides.
  - `API.py` defines all the Exo API exposed to the user. Documentation of the API can be found in the section below.
  - `libs/` includes user-defined memory definitions (`memories.py`) and the custom malloc implementation.
  - `platforms/` includes user-defined instruction definitions that are part of the release. This is similar to standard library in C.
  - Other files are the core implementation of Exo (e.g., `typecheck.py` implements typecheck), but will not explain here as it is not exposed to users
2. `apps/` includes user-level application code using Exo
3. `dependencies/` includes submodules that Exo depends on
4. `examples/` includes Python notebook that was used for Demo
5. `tests/` includes unittest

### Documentation for scheduling API

#### Top-level Python function decorator
1. `@proc` decorated Python function is parsed and compiled as Exo language. Returns `Procedure` object
2. `@instr` is the same as `@proc` but takes a string of hardware instructions
3. `@config` decorates a Python class which is parsed and compile as Exo configuration object 

- `compile_procs(proc_list, path, c_file, h_file)` takes Exo proc list, path to the C and the header file, and C and the header file names. It compiles Exo procs into C files.

#### Procedure object
Introspection operations
- `name()` returns a procedure name
- `check_effects()` forces Exo to run the effect check on this procedure
- `show_effects()` prints the effects of the procedure
- `show_effect(stmt)` prints the effect of the stmt in the procedure
- `is_instr()` returns true if the procedure is `@instr`
- `get_instr()` returns the instruction string
- `get_ast()` returns QAST, which is the introspection AST representation

Execution / interpretation operations
- `compile_c(directory, filename)` compiles this procedure into C and stores in filename in directory
- `interpret(**args)` interprets this procedure

Scheduling operations
- `simplify()` Simplify the code in the procedure body. Tries to reduce expressions
        to constants and eliminate dead branches and loops. Uses branch
        conditions to simplify expressions inside the branches.
- `rename(new_name)` Rename this procedure to new\_name
- `make_instr(instr_string)` makes this procedure to instruction procedure with `instr_string`
- `partial_eval(*args, **kwargs)` specializes this procedure to the arguments.
- `set_precision(name, type)` sets the precision type of `name` to `type`
- `set_window(name, is_window)` if `is_window` is True, it sets the buffer `name` to window type, instead of a tensor type
- `set_memory(name, mem_type)` sets a buffer `name`'s memory type to `mem_type`
- `bind_config(var, config, field)` sets 
- `data_reuse(self, buf_pattern, replace_pattern)`
- `configwrite_root(self, config, field, var_pattern)`
- `configwrite_after(self, stmt_pattern, config, field, var_pattern)`
- `inline_window(self, stmt_pattern)`
- `split(self, split_var, split_const, out_vars, tail='guard', perfect=False)`
- `expand_dim(self, stmt_pat, alloc_dim_pat, indexing_pat, unsafe_disable_checks=False)`
- `add_unsafe_guard(self, stmt_pat, var_pattern)`
- `specialize(self, stmt_pat: str, conds: Union[str, List[str]])`
- `add_assertion(self, assertion)`
- `add_guard(self, stmt_pat, iter_pat, value)`
- `bound_and_guard(self, loop)`
```
        Replace
          for i in par(0, e): ...
        with
          for i in par(0, c):
            if i < e: ...
        where c is the tightest constant bound on e
        This currently only works when e is of the form x % n
```
- `fuse_loop(self, loop1, loop2)`
- `fuse_if(self, if1, if2)`
- `add_loop(self, stmt, var, hi)`
- `merge_guard(self, stmt1, stmt2)`
- `insert_pass(self, pat: str)`
- `delete_pass(self)`
- `reorder_before(self, pat)`
- `delete_config(self, stmt_pat)`
- `reorder_stmts(self, first_pat, second_pat)`
- `lift_if(self, if_pattern, n_lifts=1)`
- `assert_if(self, if_pattern, cond)`
- `partition_loop(self, var_pattern, num)`
- `reorder(self, out_var, in_var)`
- `unroll(self, unroll_var)`
- `replace(self, subproc, pattern, quiet=False)`
- `replace_all(self, subproc)`
- 



### Documentation for examples



## 3. Able to make changes


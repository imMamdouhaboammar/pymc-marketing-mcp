# Lesson 55: Evaluator Schema Fidelity and Public Tool Contract Alignment

### Context
Agent skill evaluations and trace validation (`src/marketing_mcp/skillpack/evals.py`) testing whether LLM agents execute valid recovery sequences under the FastMCP tool contract.

### What happened
The skillpack evaluator originally accepted or required synthetic arguments such as `resume_job(job_id=..., job_type=...)` in test traces. However, the actual public FastMCP tool registered in `src/marketing_mcp/mcp/tools/jobs.py` had signature `resume_job(job_id: str)`. When real LLM clients interacted with the server, passing `job_type` resulted in a Pydantic / FastMCP schema validation error (`unexpected keyword argument 'job_type'`).

### Observable symptom
Traces that passed synthetic evaluation failed when executed against the real server API with:
```text
pydantic.ValidationError: Extra inputs are not permitted [type=extra_forbidden, input_value='fit_mmm', input_type=str]
```
Or MCP tool dispatch errors rejecting calls containing parameters not declared in the tool's JSON Schema.

### Impact
- **Test-to-Production Drift**: Evaluation suites validated fictional tool interactions while real agent workflows crashed against the production API.
- **Agent Hallucination Encouragement**: Prompts and golden traces taught models to provide parameters that the server explicitly rejects.

### Incorrect assumption
Assumed evaluator traces could include helper metadata in tool argument dictionaries without checking whether the underlying FastMCP tool schema permitted those arguments.

### Root cause
**Confirmed**.
The skillpack evaluator was developed independently from the FastMCP tool definition, leading to synthetic parameters being introduced to aid evaluation logic rather than deriving evaluation state from the real contract.

### Why the architecture allowed it
Evaluator tests ran against static JSON traces rather than asserting schema conformity against the live FastMCP tool registry (`mcp.list_tools()`).

### Fix
1. Updated `evaluate_tool_trace` to validate tool call arguments strictly against real FastMCP schemas:
```python
# In src/marketing_mcp/skillpack/evals.py
unsupported_args = [arg for arg in args.keys() if arg != "job_id"]
if unsupported_args:
    reasons.append(
        f"resume_job called at step {index} with unsupported argument(s) {unsupported_args}; "
        "public MCP tool only accepts 'job_id'"
    )
```
2. Updated all 25 evals in `src/marketing_mcp/skillpack/skills/pymc-job-resilience/evals/evals.json` to use exact public signatures (`{"job_id": "..."}`).
3. Added schema validation tests asserting trace argument compatibility against tool schemas.

### Verification
- `tests/unit/test_skill_pack_contract.py::test_evaluator_rejects_resume_job_with_extra_arguments`
- `tests/unit/test_skill_pack_contract.py::test_all_evaluation_traces_conform_to_mcp_schemas`
- All 25 evaluation traces in `evals.json` pass without errors.

### Prevention rule
> **Evaluation trace fixtures and validator assertions must strictly conform to public API contracts; never inject synthetic helper fields into tool argument payloads.**

### Reusable lesson
Evaluation and benchmarking harnesses must enforce strict contract parity with production APIs. Allowing synthetic parameters in test harnesses creates a false sense of security and corrupts agent training.

### Related code
- `src/marketing_mcp/skillpack/evals.py`
- `src/marketing_mcp/mcp/tools/jobs.py`

### Related tests
- `tests/unit/test_skill_pack_contract.py`

### Status
Solved (commit `85aaedb`, merged in `69f6280`)

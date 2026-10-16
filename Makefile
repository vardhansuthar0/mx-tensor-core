.NOTPARALLEL: reproduce signoff
PYTHON ?= python3
.PHONY: reproduce model lint sim array formal mutation physical signoff clean
reproduce: verification-start model lint sim array formal mutation converter-formal product-exhaustive native-uvm code-coverage coverage-closure signoff-tests formal-negative
	$(PYTHON) scripts/summarize.py
model:
	$(PYTHON) -m pytest -q tb/test_model.py --junitxml=reports/model.xml
lint:
	$(PYTHON) scripts/lint.py
sim:
	@for l in 8 16 32; do for p in 3 4 5; do $(PYTHON) scripts/run_sim.py --lanes $$l --stages $$p > reports/sim-l$$l\_p$$p.log 2>&1 || { tail -35 reports/sim-l$$l\_p$$p.log; exit 1; }; done; done
array:
	@for m in 1 2 4; do $(PYTHON) scripts/run_engine.py --size $$m > reports/engine$$m.log 2>&1 || { tail -35 reports/engine$$m.log; exit 1; }; done
formal:
	$(PYTHON) scripts/formal.py
mutation:
	$(PYTHON) scripts/mutate.py
physical:
	$(PYTHON) scripts/physical.py
signoff: reproduce physical
	$(PYTHON) scripts/signoff_check.py
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"

.PHONY: analyze-physical
analyze-physical:
	$(PYTHON) scripts/routed_power.py physical/results/analysis-state.json
	$(PYTHON) scripts/timing_sweep.py physical/results/analysis-state.json

.PHONY: converter-formal native-uvm code-coverage check-signoff
converter-formal:
	$(PYTHON) scripts/converter_formal.py
native-uvm:
	$(PYTHON) scripts/native_uvm.py
code-coverage:
	$(PYTHON) scripts/code_coverage.py
check-signoff:
	$(PYTHON) scripts/signoff_check.py

.PHONY: signoff-tests
signoff-tests:
	$(PYTHON) -m pytest -q tb/test_signoff.py

.PHONY: verification-start
verification-start:
	$(PYTHON) scripts/provenance.py

.PHONY: arithmetic-bounded
arithmetic-bounded:
	$(PYTHON) scripts/arithmetic_formal.py

.PHONY: formal-negative
formal-negative:
	$(PYTHON) scripts/formal_negative.py

.PHONY: product-exhaustive coverage-constants
product-exhaustive:
	$(PYTHON) scripts/product_exhaustive.py
coverage-constants:
	$(PYTHON) scripts/coverage_constants.py

.PHONY: coverage-paths coverage-closure
coverage-paths:
	$(PYTHON) scripts/coverage_paths.py
coverage-closure: coverage-constants coverage-paths
	$(PYTHON) scripts/coverage_closure.py

.PHONY: streaming-formal
streaming-formal:
	$(PYTHON) scripts/streaming_formal.py

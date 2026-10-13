PYTHON ?= python3
.PHONY: reproduce model lint sim array formal mutation physical signoff clean
reproduce: model lint sim array formal mutation
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
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('build', ignore_errors=True)"

.PHONY: analyze-physical
analyze-physical:
	$(PYTHON) scripts/routed_power.py physical/results/analysis-state.json
	$(PYTHON) scripts/timing_sweep.py physical/results/analysis-state.json

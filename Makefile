PY ?= python

.PHONY: check test splits demo viewer logs stress budget docker-build docker-check

check:          ## single offline check (tests, data, rewards, reproducibility, leaks)
	$(PY) -m auditgym check

test:
	$(PY) -m unittest discover -s tests -t .

splits:         ## regenerate episodes/train and episodes/dev
	$(PY) -m auditgym build-splits

logs:           ## trajectories and grades for the open splits
	$(PY) -m auditgym run --episodes episodes/train episodes/dev --policies random,recon,flag_all,oracle,auditor,silent --out runs/train_dev

stress:         ## generator stress run: 300 random + 17 extreme configurations -> runs/stress/report.md
	$(PY) -m auditgym stress --n 300

budget:         ## auditor and recon on dev at 20, 50 and 100 steps -> runs/budget/summary.md
	$(PY) -m auditgym budget

demo:
	$(PY) -m auditgym demo

viewer:
	$(PY) -m auditgym viewer

docker-build:
	docker build -t auditgym .

docker-check:
	docker run --rm --network none --cpus 2 --memory 4g auditgym

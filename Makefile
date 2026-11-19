PY ?= python

.PHONY: check test splits demo viewer logs docker-build docker-check

check:          ## single offline check (tests, data, rewards, reproducibility, leaks)
	$(PY) -m auditgym check

test:
	$(PY) -m unittest discover -s tests -t .

splits:         ## regenerate episodes/train and episodes/dev
	$(PY) -m auditgym build-splits

logs:           ## trajectories and grades for the open splits
	$(PY) -m auditgym run --episodes episodes/train episodes/dev --policies random,recon,flag_all,oracle,auditor --out runs/train_dev

demo:
	$(PY) -m auditgym demo

viewer:
	$(PY) -m auditgym viewer

docker-build:
	docker build -t auditgym .

docker-check:
	docker run --rm --network none --cpus 2 --memory 4g auditgym

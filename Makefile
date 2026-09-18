URL ?= http://localhost:8080
IMAGE ?= ghcr.io/USERNAME/gridwise
TAG ?= v1

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

verify:
	python tools/harness.py --url $(URL)
	python tools/harness.py --url $(URL) --paraphrase
	python tools/harness.py --url $(URL) --adversarial
	python tools/harness.py --url $(URL) --soak

build:
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t $(IMAGE):$(TAG) --push .

local-image:
	docker build -t gridwise:local .
	docker run --rm -p 8080:8080 -e OFFLINE_FALLBACK=1 gridwise:local

deploy-cloudrun:
	gcloud run deploy gridwise --image $(IMAGE):$(TAG) --region asia-south1 \
		--allow-unauthenticated --min-instances=1 --memory 1Gi --timeout 60 \
		--set-env-vars GEMINI_API_KEY=$(GEMINI_API_KEY),GROQ_API_KEY=$(GROQ_API_KEY)

deploy-fly:
	fly deploy --image $(IMAGE):$(TAG)

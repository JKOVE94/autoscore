# Thin wrapper around ./run — see `./run help`
.PHONY: bootstrap setup dev docker docker-down doctor test stop clean

bootstrap:   ; @./run bootstrap
setup:       ; @./run setup
dev:         ; @./run dev
docker:      ; @./run docker
docker-down: ; @./run docker-down
doctor:      ; @./run doctor
test:        ; @./run test
stop:        ; @./run stop
clean:       ; @./run clean

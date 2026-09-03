# Thin wrapper around ./run — see `./run help`
.PHONY: start dev bootstrap setup docker docker-down k8s k8s-down doctor test stop clean

start:       ; @./run start
dev:         ; @./run dev
bootstrap:   ; @./run bootstrap
setup:       ; @./run setup
docker:      ; @./run docker
docker-down: ; @./run docker-down
k8s:         ; @./run k8s
k8s-down:    ; @./run k8s-down
doctor:      ; @./run doctor
test:        ; @./run test
stop:        ; @./run stop
clean:       ; @./run clean

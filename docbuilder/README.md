# docbuilder

Generate `pdf|fo|csv` files from `xml` files according to appropriate `xslt`.

## Local Development

```sh
docker build --tag docbuilder:1.0 .

docker run \
  -e "CI_PROJECT_DIR=/var/project" \
  -e "CI_PROJECT_NAME=<project-name>" \
  -v "/path/to/doc/project:/var/project" \
  --name "docbuilder" \
  --rm \
  docbuilder:1.0
```

see <project-dir>/target for the generated documents.

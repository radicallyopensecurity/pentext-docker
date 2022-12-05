# pentext-docker

Scripts and GitLab runners for document generation. 

## Usage

See the `scripts` directory and `Dockerfile` in each package to see what each package does.

To build a runner:

```sh
docker build --tag <package>:1.0 <any-build-args> .
```

## Packages

### [`/convert`](/convert)

Pre-process `.xml` files, performing conversions and formatting where necessary.

### [`/docbuilder`](/docbuilder/)

Generate `pdf|fo|csv` files from `xml` files according to appropriate `xslt`.

### [`/off2rep`](/off2rep/)

Convert pentest quotation into a report.

### [`/quickscope`](/quickscope/)

Convert quickscope into a quotation.

## Docker

```sh
cp .env.sample .env
# optionally set a fixed GITLAB_TOKEN
echo 'GITLAB_TOKEN={{MY_GITLAB_TOKEN}}' >> .env
echo 'EXTRA_COOKIES=_eyed_p_session={{MY_EYEDP_COOKIE}}' >> .env
docker compose build
docker compose up -d
```

```sh
export GITLAB_PROJECT_ID=1234
export PENTEXT_DIR=/path/to/my-pentest
docker compose run \
	-v "$PENTEXT_DIR:/pentext" \
	-e CI_PROJECT_ID=$GITLAB_PROJECT_ID \
	convert
```


## License

[LICENSE.txt](/LICENSE.txt)
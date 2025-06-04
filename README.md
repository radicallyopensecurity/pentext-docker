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

#### ENV: `MERGE_STRATEGY`

When a finding XML file already exists, the following strategies can be used to update XML data from GitLab Issues:

- `RETEST`: Update finding `status` and `<update>` tags
- `META`: Update finding `id`, `threatLevel`, `type` and `status`
- `LABELS`:
- `TITLE`:
- `DESCRIPTION`
- `TECHNICALDESCRIPTION`
- `RECOMMENDATION`
- `IMPACT`

```sh
# only update retest results and finding meta-data
MERGE_STRATEGY="RETEST|META"
```

### [`/docbuilder`](/docbuilder/)

Generate `pdf|fo|csv` files from `xml` files according to appropriate `xslt`.

### [`/off2rep`](/off2rep/)

Convert pentest quotation into a report.

### [`/quickscope`](/quickscope/)

Convert quickscope into a quotation.

## Docker Compose

### Use with caution

🚨⚠️ **Security warning**: `GITLAB_TOKEN` will be accessible from the [convert](./convert/) container and your private EyeDP Cookie is not supposed to be shared or stored on disk. The [proxy](./proxy/) setup is a hack to separate the convert container from the Internet and local network and from the secret EyeDP Cookie, but must be used with caution. The credential will be built into the image and stored on disk. Only use on a host you fully trust and nobody else has access to.

### Configure and run EyeDP Proxy

```sh
cp .env.sample .env
# optionally set a fixed GITLAB_TOKEN (read_api, read_repo)
echo 'GITLAB_TOKEN={{MY_GITLAB_TOKEN}}' >> .env
echo 'EXTRA_COOKIES=_eyed_p_session={{MY_EYEDP_COOKIE}}' >> .env
docker compose build
docker compose up -d
```

### Convert GitLab project to Pentext XML

```sh
export GITLAB_PROJECT_ID=1234
export PENTEXT_DIR=/path/to/my-pentest
docker compose run --rm \
	-v "$PENTEXT_DIR:/pentext" \
	-e CI_PROJECT_ID=$GITLAB_PROJECT_ID \
	convert
```

### Build PDF from local Pentext XML

```sh
export PENTEXT_DIR=/path/to/my-pentest
docker compose run --rm \
	-v "$PENTEXT_DIR:/pentext" \
	docbuilder
```

## License

[GPL-2.0](/LICENSE)

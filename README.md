# pentext-docker

Scripts and GitLab runners for document generation. 

## Usage

See the `scripts` directory and `Dockerfile` in each package to see what each package does.

To build a runner:

```sh
docker build --tag <package>:1.0 <any-build-args> .
```

## Packages

## [`/convert`](/convert)

Pre-process `.xml` files, performing conversions and formatting where necessary.

## [`/docbuilder`](/docbuilder/)

Generate `pdf|fo|csv` files from `xml` files according to appropriate `xslt`.

## [`/off2rep`](/off2rep/)

Convert pentest quotation into a report.

## [`/quickscope`](/quickscope/)

Convert quickscope into a quotation.

## License

[LICENSE.txt](/LICENSE.txt)
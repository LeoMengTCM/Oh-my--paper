# 从已安装的公开 R 数据包读取原表，不安装包、不生成临床审批记录。
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 1L)
for (package in c("metadat", "jsonlite")) {
  if (!requireNamespace(package, quietly = TRUE)) stop("Required package: ", package)
}
data("dat.bcg", package = "metadat", envir = environment())
utils::write.csv(dat.bcg, file.path(args[1], "dataset.csv"), row.names = FALSE)
description <- utils::packageDescription("metadat")
source <- list(dataset = "metadat::dat.bcg", version = description$Version,
               license = description$License,
               package_url = "https://CRAN.R-project.org/package=metadat",
               allocation_counts = as.list(table(dat.bcg$alloc)))
jsonlite::write_json(source, file.path(args[1], "source.json"), auto_unbox = TRUE, pretty = TRUE)

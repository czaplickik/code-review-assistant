#!/usr/bin/env python3
"""Mechanical refactor applied as the UNCOMMITTED change of java-05-large-refactor.

1. SLF4J logger fields -> Lombok @Slf4j (every class that declares `Logger log`).
2. Package rename com.example.shop.common.util -> com.example.shop.common.support
   (files moved, package declarations and imports updated everywhere).
3. pom.xml gets Lombok; conventions.md and lombok.config updated accordingly.

Hidden among the noise (see EXPECTED.md) are three real behaviour changes:
  a. WishlistEntryService#delete no longer checks ownership,
  b. BundleService#replaceItems lost @Transactional (multi-write method),
  c. PromotionCampaignService.MAX_DISCOUNT_PERCENT 30 -> 50.

Usage: python3 -I generate.py <target-dir>   (stdlib only)
"""
import os
import re
import shutil
import sys

OLD_PKG = "com.example.shop.common.util"
NEW_PKG = "com.example.shop.common.support"
LOGGER_FIELD = re.compile(r"^\s*private static final Logger log = LoggerFactory\.getLogger\(\w+\.class\);\s*$")
LOMBOK_IMPORT = "import lombok.extern.slf4j.Slf4j;"
CLASS_DECL = re.compile(r"^(public\s+)?(final\s+|abstract\s+)*(class|record|enum|interface)\s+\w+")


def to_slf4j(text):
    if "LoggerFactory.getLogger" not in text:
        return text
    lines = text.split("\n")
    out = []
    for line in lines:
        if LOGGER_FIELD.match(line):
            continue
        if line in ("import org.slf4j.Logger;", "import org.slf4j.LoggerFactory;"):
            continue
        out.append(line)
    # collapse the blank-line pair left behind by the removed field
    collapsed = []
    for line in out:
        if line.strip() == "" and collapsed and collapsed[-1].strip() == "":
            continue
        collapsed.append(line)
    lines = collapsed

    # insert the Lombok import in sorted position within the import block
    import_idx = [i for i, l in enumerate(lines) if l.startswith("import ") and not l.startswith("import static ")]
    pos = next((i for i in import_idx if lines[i] > LOMBOK_IMPORT), import_idx[-1] + 1)
    lines.insert(pos, LOMBOK_IMPORT)

    # @Slf4j above the first type-level annotation of the top-level class
    decl = next(i for i, l in enumerate(lines) if CLASS_DECL.match(l))
    top = decl
    while top > 0 and lines[top - 1].startswith("@"):
        top -= 1
    lines.insert(top, "@Slf4j")
    return "\n".join(lines)


def rename_package(text):
    return text.replace(OLD_PKG + ".", NEW_PKG + ".").replace("package " + OLD_PKG + ";", "package " + NEW_PKG + ";")


def replace_once(path, old, new):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if text.count(old) != 1:
        sys.exit(f"generate.py: expected exactly one match in {path}:\n{old}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))


def main(target):
    src = os.path.join(target, "src")
    for root, _, files in os.walk(src):
        for name in files:
            if not name.endswith(".java"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            new = rename_package(to_slf4j(text))
            if new != text:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new)

    old_dir = os.path.join(target, "src/main/java", *OLD_PKG.split("."))
    new_dir = os.path.join(target, "src/main/java", *NEW_PKG.split("."))
    os.makedirs(new_dir, exist_ok=True)
    for name in sorted(os.listdir(old_dir)):
        shutil.move(os.path.join(old_dir, name), os.path.join(new_dir, name))
    os.rmdir(old_dir)

    # --- build + docs ----------------------------------------------------------------------
    pom = os.path.join(target, "pom.xml")
    replace_once(pom, """        <dependency>
            <groupId>io.micrometer</groupId>""", """        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>""")
    replace_once(pom, """            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>""", """            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                            <version>${lombok.version}</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>""")
    conventions = os.path.join(target, "docs/architecture/conventions.md")
    replace_once(conventions,
                 "- One public constructor per Spring bean; no Lombok `@RequiredArgsConstructor` (we do not use Lombok).",
                 "- One public constructor per Spring bean; no Lombok `@RequiredArgsConstructor`. Lombok is allowed\n"
                 "  for `@Slf4j` only.")
    replace_once(conventions,
                 "- SLF4J only: `private static final Logger log = LoggerFactory.getLogger(Foo.class);`",
                 "- SLF4J only, via Lombok `@Slf4j` on the class (field name `log`). No hand-written logger fields.")
    with open(os.path.join(target, "lombok.config"), "w", encoding="utf-8") as fh:
        fh.write("config.stopBubbling = true\nlombok.log.fieldName = log\nlombok.addLombokGeneratedAnnotation = true\n")

    # --- the three real changes hidden in the noise -----------------------------------------
    catalog = os.path.join(target, "src/main/java/com/example/shop/catalog")

    wishlist = os.path.join(catalog, "wishlist/WishlistEntryService.java")
    replace_once(wishlist, """        Long ownerId = jdbc.sql("SELECT user_id FROM wishlist_entries WHERE id = :id")
                .param("id", id)
                .query(Long.class)
                .optional()
                .orElseThrow(() -> new ResourceNotFoundException("WishlistEntry", id));
        if (!ownerId.equals(currentUserId)) {
            throw new ForbiddenOperationException("WishlistEntry " + id + " belongs to another user");
        }
        jdbc.sql("DELETE FROM wishlist_entries WHERE id = :id").param("id", id).update();
""", """        int deleted = jdbc.sql("DELETE FROM wishlist_entries WHERE id = :id").param("id", id).update();
        if (deleted == 0) {
            throw new ResourceNotFoundException("WishlistEntry", id);
        }
""")
    replace_once(wishlist, "import com.example.shop.common.error.ForbiddenOperationException;\n", "")

    bundle = os.path.join(catalog, "bundle/BundleService.java")
    replace_once(bundle, "    @Transactional\n    public BundleDto replaceItems(", "    public BundleDto replaceItems(")
    replace_once(bundle, "import org.springframework.transaction.annotation.Transactional;\n", "")

    campaign = os.path.join(catalog, "promotion/PromotionCampaignService.java")
    replace_once(campaign, 'MAX_DISCOUNT_PERCENT = new BigDecimal("30");', 'MAX_DISCOUNT_PERCENT = new BigDecimal("50");')


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("usage: generate.py <target-dir>")
    main(sys.argv[1])

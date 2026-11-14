#!/usr/bin/env python3
"""Inflates java-spring-shop with the catalogue read-model modules before the base commit.

Generates com.example.shop.catalog.<area>.<Name>{Dto,Mapper,Service,Controller} for 48
entities (192 Java files) plus the matching Flyway migration. The code is JdbcClient based,
uses SLF4J logger fields and the common.util helpers, which is what generate.py later
refactors. Usage: python3 -I prepare.py <target-dir>   (stdlib only)
"""
import os
import re
import sys

# (area, Name, url path, table, fields, features)
#   field spec: name:<S<max>|D|I|L|B|T>[!]   or  slug:slug   ("!" = required)
#   features:   search=<col>; soft; tx; owned; role=<ROLE>; order=<sql>; size=<max page>;
#               extra=<key>; unique=<col,col>
ENTITIES = [
    ("attribute", "AttributeDefinition", "attribute-definitions", "attribute_definitions",
     "code:S64!, label:S120!, dataType:S20!, unit:S16, filterable:B, position:I", "search=label;tx;order=position"),
    ("attribute", "AttributeValue", "attribute-values", "attribute_values",
     "attributeId:L!, productId:L!, valueText:S500, valueNumber:D", "order=attribute_id;size=200"),
    ("attribute", "AttributeGroup", "attribute-groups", "attribute_groups",
     "name:S120!, slug:slug, position:I", "soft;order=position"),
    ("attribute", "AttributeOption", "attribute-options", "attribute_options",
     "attributeId:L!, value:S120!, label:S120!, position:I", "tx;order=position"),

    ("brand", "Brand", "brands", "brands",
     "name:S120!, slug:slug, description:S2000, websiteUrl:S300, countryCode:S2", "search=name;soft;tx;order=name"),
    ("brand", "BrandLogo", "brand-logos", "brand_logos",
     "brandId:L!, url:S500!, altText:S200, widthPx:I, heightPx:I", "order=brand_id"),
    ("brand", "BrandCollection", "brand-collections", "brand_collections",
     "brandId:L!, name:S120!, slug:slug, season:S20, startsAt:T", "soft;order=starts_at DESC"),
    ("brand", "BrandPartner", "brand-partners", "brand_partners",
     "brandId:L!, partnerName:S200!, contactEmail:S254, commissionPercent:D", "tx;order=partner_name"),

    ("bundle", "Bundle", "bundles", "bundles",
     "name:S120!, slug:slug, description:S2000, priceAmount:D!, itemCount:I", "search=name;order=name;extra=bundle_replace"),
    ("bundle", "BundleItem", "bundle-items", "bundle_items",
     "bundleId:L!, productId:L!, position:I, quantity:I, note:S500", "order=position"),
    ("bundle", "BundleOffer", "bundle-offers", "bundle_offers",
     "bundleId:L!, title:S200!, discountAmount:D, validFrom:T, validUntil:T", "soft;tx;order=valid_from DESC"),
    ("bundle", "BundleRule", "bundle-rules", "bundle_rules",
     "bundleId:L!, ruleType:S40!, expression:S1000!, priority:I", "tx;order=priority"),

    ("collection", "Collection", "collections", "collections",
     "name:S120!, slug:slug, description:S2000, position:I, published:B", "search=name;soft;tx;order=position"),
    ("collection", "CollectionEntry", "collection-entries", "collection_entries",
     "collectionId:L!, productId:L!, position:I, pinned:B, badge:S40", "order=position;size=200"),
    ("collection", "SeasonalCollection", "seasonal-collections", "seasonal_collections",
     "name:S120!, slug:slug, season:S20!, startsAt:T, endsAt:T", "soft;order=starts_at DESC"),
    ("collection", "CollectionBanner", "collection-banners", "collection_banners",
     "collectionId:L!, imageUrl:S500!, headline:S160, ctaLabel:S40, ctaUrl:S300", "tx;order=collection_id"),

    ("inventory", "StockLevel", "stock-levels", "stock_levels",
     "productId:L!, warehouseId:L!, onHand:I!, reserved:I!, reorderPoint:I, binLocation:S32", "tx;order=product_id;size=200;extra=stock_adjust"),
    ("inventory", "Warehouse", "warehouses", "warehouses",
     "code:S16!, name:S120!, city:S120, countryCode:S2!, notes:S1000", "search=name;soft;order=code"),
    ("inventory", "StockReservation", "stock-reservations", "stock_reservations",
     "productId:L!, warehouseId:L!, orderId:L, quantity:I!, expiresAt:T, reference:S64", "tx;order=expires_at"),
    ("inventory", "StockMovement", "stock-movements", "stock_movements",
     "productId:L!, warehouseId:L!, delta:I!, reason:S500!, occurredAt:T", "order=occurred_at DESC;size=500"),

    ("media", "ProductImage", "product-images", "product_images",
     "productId:L!, url:S500!, altText:S200, position:I, primaryImage:B", "tx;order=position"),
    ("media", "ProductVideo", "product-videos", "product_videos",
     "productId:L!, url:S500!, title:S200, durationSeconds:I", "order=product_id"),
    ("media", "MediaAsset", "media-assets", "media_assets",
     "fileName:S255!, contentType:S100!, sizeBytes:L, storageKey:S500!, checksum:S64", "search=file_name;order=file_name"),
    ("media", "ImageVariant", "image-variants", "image_variants",
     "imageId:L!, variant:S20!, url:S500!, widthPx:I, heightPx:I", "tx;order=image_id"),

    ("pricing", "PriceList", "price-lists", "price_lists",
     "code:S32!, name:S120!, currency:S3!, validFrom:T, validUntil:T", "soft;tx;order=code"),
    ("pricing", "PriceListEntry", "price-list-entries", "price_list_entries",
     "priceListId:L!, productId:L!, amount:D!, minQuantity:I, note:S500", "order=product_id;size=500;extra=price_lookup"),
    ("pricing", "PriceRule", "price-rules", "price_rules",
     "name:S120!, expression:S1000!, priority:I, enabled:B", "tx;order=priority"),
    ("pricing", "TaxClass", "tax-classes", "tax_classes",
     "code:S16!, name:S120!, ratePercent:D!, countryCode:S2!", "search=name;order=code"),

    ("promotion", "PromotionCampaign", "promotion-campaigns", "promotion_campaigns",
     "name:S120!, slug:slug, discountPercent:D!, startsAt:T, endsAt:T, description:S2000",
     "soft;tx;order=starts_at DESC;extra=campaign_cap"),
    ("promotion", "PromotionCode", "promotion-codes", "promotion_codes",
     "campaignId:L!, code:S32!, maxRedemptions:I, redemptions:I", "tx;order=code;extra=code_redeem;unique=code"),
    ("promotion", "PromotionBanner", "promotion-banners", "promotion_banners",
     "campaignId:L!, imageUrl:S500!, headline:S160, position:I", "order=position"),
    ("promotion", "PromotionEligibility", "promotion-eligibilities", "promotion_eligibilities",
     "campaignId:L!, productId:L, categoryId:L, excluded:B, note:S500", "order=campaign_id"),

    ("review", "ProductReview", "product-reviews", "product_reviews",
     "productId:L!, authorName:S120!, rating:I!, title:S160, body:S4000, approved:B",
     "role=SUPPORT;order=id DESC;extra=review_approve"),
    ("review", "ReviewVote", "review-votes", "review_votes",
     "reviewId:L!, voterId:L!, helpful:B!, comment:S500", "order=review_id;extra=vote_upsert;unique=review_id,voter_id"),
    ("review", "ReviewReport", "review-reports", "review_reports",
     "reviewId:L!, reason:S500!, status:S20!", "role=SUPPORT;tx;order=id DESC"),
    ("review", "ReviewSummary", "review-summaries", "review_summaries",
     "productId:L!, averageRating:D, reviewCount:I, lastReviewAt:T, headline:S160", "order=product_id;unique=product_id"),

    ("search", "SearchSynonym", "search-synonyms", "search_synonyms",
     "term:S120!, synonyms:S1000!, locale:S8", "search=term;tx;order=term"),
    ("search", "SearchRedirect", "search-redirects", "search_redirects",
     "query:S200!, targetUrl:S500!, active:B", "order=query;extra=redirect_resolve"),
    ("search", "SearchBoost", "search-boosts", "search_boosts",
     "productId:L!, boostFactor:D!, reason:S500, expiresAt:T", "tx;order=boost_factor DESC"),
    ("search", "SearchFacet", "search-facets", "search_facets",
     "attributeId:L!, label:S120!, slug:slug, position:I", "soft;order=position"),

    ("shipping", "ShippingMethod", "shipping-methods", "shipping_methods",
     "code:S32!, name:S120!, carrier:S60!, description:S2000, trackingUrlTemplate:S500", "search=name;soft;tx;order=name"),
    ("shipping", "ShippingZone", "shipping-zones", "shipping_zones",
     "name:S120!, slug:slug, countryCodes:S1000!", "tx;order=name"),
    ("shipping", "ShippingRate", "shipping-rates", "shipping_rates",
     "methodId:L!, zoneId:L!, maxWeightGrams:I!, priceAmount:D!, label:S80", "order=max_weight_grams;extra=rate_quote"),
    ("shipping", "PackageDimension", "package-dimensions", "package_dimensions",
     "productId:L!, lengthMm:I!, widthMm:I!, heightMm:I!, weightGrams:I!, note:S500", "order=product_id"),

    ("wishlist", "Wishlist", "wishlists", "wishlists",
     "name:S120!, slug:slug, isPublic:B", "owned;tx;order=name"),
    ("wishlist", "WishlistEntry", "wishlist-entries", "wishlist_entries",
     "wishlistId:L!, productId:L!, note:S500, addedAt:T", "owned;tx;order=added_at DESC"),
    ("wishlist", "WishlistShare", "wishlist-shares", "wishlist_shares",
     "wishlistId:L!, sharedWithEmail:S254!, token:S64!, expiresAt:T", "owned;order=id DESC"),
    ("wishlist", "WishlistReminder", "wishlist-reminders", "wishlist_reminders",
     "wishlistId:L!, remindAt:T!, channel:S20!, message:S500", "owned;order=remind_at"),
]

TYPES = {"S": "String", "D": "BigDecimal", "I": "Integer", "L": "Long", "B": "Boolean", "T": "Instant"}
SQL_TYPES = {"D": "NUMERIC(12,2)", "I": "INTEGER", "L": "BIGINT", "B": "BOOLEAN", "T": "TIMESTAMPTZ"}
UTIL = "com.example.shop.common.util"


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def words(name):
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()


class Field:
    def __init__(self, spec):
        name, kind = [p.strip() for p in spec.split(":")]
        self.name = name
        self.required = kind.endswith("!")
        kind = kind.rstrip("!")
        self.slug = kind == "slug"
        if self.slug:
            kind = "S140"
        self.kind = kind[0]
        self.max = int(kind[1:]) if self.kind == "S" and len(kind) > 1 else None
        self.jtype = TYPES[self.kind]
        self.column = snake(name)


class Entity:
    def __init__(self, area, name, path, table, fields, features):
        self.area, self.name, self.path, self.table = area, name, path, table
        self.fields = [Field(f) for f in fields.split(",")]
        self.feat = {}
        for item in features.split(";"):
            key, _, value = item.partition("=")
            self.feat[key.strip()] = value.strip() or True
        self.pkg = "com.example.shop.catalog." + area
        self.owned = "owned" in self.feat
        self.soft = "soft" in self.feat
        self.tx = "tx" in self.feat
        self.role = self.feat.get("role", "ADMIN")
        self.order = self.feat.get("order", "id")
        self.max_page = int(self.feat.get("size", 100))
        self.extra = self.feat.get("extra")
        self.search = self.feat.get("search")
        strings = [f for f in self.fields if f.kind == "S" and not f.slug]
        names = [f for f in strings if f.name == "name"]
        candidates = names or [f for f in strings if f.required] or strings
        if not candidates:
            raise ValueError(name + ' needs at least one String field')
        self.slug_source = candidates[0]
        self.label = words(name)

    @property
    def dto(self):
        return self.name + "Dto"


ENTS = [Entity(*e) for e in ENTITIES]


def imports_block(imports):
    return "\n".join("import " + i + ";" for i in sorted(imports))


def write(rel_dir, cls, content):
    directory = os.path.join(TARGET, "src/main/java", rel_dir.replace(".", "/"))
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, cls + ".java"), "w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------------------------
# DTO
# ---------------------------------------------------------------------------------------------
def dto_annotations(e, f, imports):
    v = "jakarta.validation.constraints."
    out = []
    if f.kind == "S":
        if f.required:
            out.append("@NotBlank")
            imports.add(v + "NotBlank")
        if f.name.endswith("Email"):
            out.append("@Email")
            imports.add(v + "Email")
        if f.name in ("countryCode", "currency"):
            n = 2 if f.name == "countryCode" else 3
            out.append('@Pattern(regexp = "[A-Z]{%d}")' % n)
            imports.add(v + "Pattern")
        elif f.slug:
            out.append('@Pattern(regexp = "[a-z0-9-]+")')
            imports.add(v + "Pattern")
        out.append("@Size(max = %d)" % f.max)
        imports.add(v + "Size")
    else:
        if f.required:
            out.append("@NotNull")
            imports.add(v + "NotNull")
        if f.kind == "D":
            out.append('@DecimalMin("0.00")')
            imports.add(v + "DecimalMin")
        elif f.kind == "I" and f.name != "delta":
            if f.name == "rating":
                out += ["@Min(1)", "@Max(5)"]
                imports.update([v + "Min", v + "Max"])
            else:
                out.append("@PositiveOrZero")
                imports.add(v + "PositiveOrZero")
        elif f.kind == "L":
            out.append("@Positive")
            imports.add(v + "Positive")
    return out


def gen_dto(e):
    imports = {UTIL + ".Texts"}
    comps = ["        Long id"]
    for f in e.fields:
        ann = dto_annotations(e, f, imports)
        comps.append("        " + " ".join(ann + [f.jtype, f.name]))
        if f.kind == "D":
            imports.add("java.math.BigDecimal")
        if f.kind == "T":
            imports.add("java.time.Instant")
    trims = ["        %s = Texts.trimToNull(%s);" % (f.name, f.name) for f in e.fields if f.kind == "S"]
    owner = " Rows are scoped to the owning user." if e.owned else ""
    return f"""package {e.pkg};

{imports_block(imports)}

/** Read/write model for {{@code {e.table}}}.{owner} */
public record {e.dto}(
{(","+chr(10)).join(comps)}) {{

    public {e.dto} {{
{chr(10).join(trims)}
    }}
}}
"""


# ---------------------------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------------------------
def gen_mapper(e):
    imports = {"java.sql.ResultSet", "java.sql.SQLException", "java.util.LinkedHashMap", "java.util.Map",
               "org.springframework.jdbc.core.RowMapper", "org.springframework.stereotype.Component"}
    reads = ['                rs.getLong("id")']
    params = []
    used_util = False
    has_instant = False
    for f in e.fields:
        c = f.column
        if f.kind == "S":
            reads.append(f'                rs.getString("{c}")')
        elif f.kind == "D":
            reads.append(f'                rs.getBigDecimal("{c}")')
        elif f.kind == "T":
            reads.append(f'                toInstant(rs.getTimestamp("{c}"))')
            has_instant = True
        else:
            reads.append(f'                rs.getObject("{c}", {f.jtype}.class)')

        if f.slug:
            src = e.slug_source.name
            params.append(f'        params.put("{f.name}", dto.{f.name}() != null ? dto.{f.name}() : Slugs.slugify(dto.{src}()));')
            imports.add(UTIL + ".Slugs")
            used_util = True
        elif f.kind == "S" and f.max >= 500:
            params.append(f'        params.put("{f.name}", Texts.abbreviate(dto.{f.name}(), {f.max}));')
            imports.add(UTIL + ".Texts")
            used_util = True
        elif f.kind == "T":
            params.append(f'        params.put("{f.name}", dto.{f.name}() == null ? null : Timestamp.from(dto.{f.name}()));')
        else:
            params.append(f'        params.put("{f.name}", dto.{f.name}());')
    if not used_util:
        first = next(i for i, f in enumerate(e.fields) if f.kind == "S")
        f = e.fields[first]
        params[first] = f'        params.put("{f.name}", Texts.trimToNull(dto.{f.name}()));'
        imports.add(UTIL + ".Texts")
    helper = ""
    if has_instant:
        imports.update(["java.sql.Timestamp", "java.time.Instant"])
        helper = """
    private static Instant toInstant(Timestamp timestamp) {
        return timestamp == null ? null : timestamp.toInstant();
    }
"""
    return f"""package {e.pkg};

{imports_block(imports)}

/** Maps {{@code {e.table}}} rows to {{@link {e.dto}}} and back to named SQL parameters. */
@Component
public class {e.name}Mapper implements RowMapper<{e.dto}> {{

    @Override
    public {e.dto} mapRow(ResultSet rs, int rowNum) throws SQLException {{
        return new {e.dto}(
{(","+chr(10)).join(reads)});
    }}

    public Map<String, Object> toParams({e.dto} dto) {{
        Map<String, Object> params = new LinkedHashMap<>();
{chr(10).join(params)}
        return params;
    }}
{helper}}}
"""


# ---------------------------------------------------------------------------------------------
# Extras: hand-written methods for a handful of entities
# ---------------------------------------------------------------------------------------------
EXTRAS = {
    "bundle_replace": {
        "service_imports": ["org.springframework.transaction.annotation.Transactional"],
        "service": """
    /** Replaces the bundle content: removes all items, re-inserts them in order and updates the item count. */
    @Transactional
    public BundleDto replaceItems(Long bundleId, List<Long> productIds) {
        get(bundleId);
        jdbc.sql("DELETE FROM bundle_items WHERE bundle_id = :bundleId")
                .param("bundleId", bundleId)
                .update();
        int position = 0;
        for (Long productId : productIds) {
            jdbc.sql("INSERT INTO bundle_items (bundle_id, product_id, position, quantity) VALUES (:bundleId, :productId, :position, 1)")
                    .param("bundleId", bundleId)
                    .param("productId", productId)
                    .param("position", position++)
                    .update();
        }
        jdbc.sql("UPDATE bundles SET item_count = :count, updated_at = now() WHERE id = :bundleId")
                .param("count", productIds.size())
                .param("bundleId", bundleId)
                .update();
        log.info("Bundle items replaced bundleId={} items={}", bundleId, productIds.size());
        return get(bundleId);
    }
""",
        "controller_imports": ["jakarta.validation.constraints.NotEmpty", "jakarta.validation.constraints.NotNull"],
        "controller": """
    @PutMapping("/{id}/items")
    @PreAuthorize("hasRole('ADMIN')")
    public BundleDto replaceItems(@PathVariable Long id, @RequestBody @NotEmpty List<@NotNull Long> productIds) {
        return service.replaceItems(id, productIds);
    }
""",
    },
    "stock_adjust": {
        "service_imports": ["com.example.shop.common.error.BusinessRuleException"],
        "service": """
    @Transactional
    public StockLevelDto adjust(Long id, int delta, String reason) {
        int updated = jdbc.sql("UPDATE stock_levels SET on_hand = on_hand + :delta, updated_at = now() "
                        + "WHERE id = :id AND on_hand + :delta >= reserved")
                .param("delta", delta)
                .param("id", id)
                .update();
        if (updated == 0) {
            get(id);
            throw new BusinessRuleException("STOCK_BELOW_RESERVED",
                    "Adjustment would drop stock level " + id + " below the reserved quantity");
        }
        StockLevelDto level = get(id);
        jdbc.sql("INSERT INTO stock_movements (product_id, warehouse_id, delta, reason, occurred_at) "
                        + "VALUES (:productId, :warehouseId, :delta, :reason, now())")
                .param("productId", level.productId())
                .param("warehouseId", level.warehouseId())
                .param("delta", delta)
                .param("reason", reason)
                .update();
        log.info("Stock adjusted stockLevelId={} delta={} reason={}", id, delta, reason);
        return level;
    }
""",
        "controller": """
    @PostMapping("/{id}/adjustments")
    @PreAuthorize("hasRole('ADMIN')")
    public StockLevelDto adjust(@PathVariable Long id, @RequestParam int delta, @RequestParam String reason) {
        return service.adjust(id, delta, reason);
    }
""",
    },
    "price_lookup": {
        "service_imports": ["com.example.shop.common.error.BusinessRuleException"],
        "service": """
    public List<PriceListEntryDto> findForProducts(Long priceListId, List<Long> productIds) {
        if (productIds.isEmpty()) {
            return List.of();
        }
        if (productIds.size() > MAX_PAGE_SIZE) {
            throw new BusinessRuleException("TOO_MANY_PRODUCTS", "At most " + MAX_PAGE_SIZE + " products per lookup");
        }
        return jdbc.sql(SELECT + " WHERE price_list_id = :priceListId AND product_id IN (:productIds)")
                .param("priceListId", priceListId)
                .param("productIds", productIds)
                .query(mapper)
                .list();
    }
""",
        "controller": """
    @GetMapping("/lookup")
    public List<PriceListEntryDto> lookup(@RequestParam Long priceListId, @RequestParam List<Long> productIds) {
        return service.findForProducts(priceListId, productIds);
    }
""",
    },
    "campaign_cap": {
        "service_imports": ["com.example.shop.common.error.BusinessRuleException", "java.math.BigDecimal"],
        "constants": """
    /** Campaigns may never promise more than the checkout discount cap (BR-7). */
    static final BigDecimal MAX_DISCOUNT_PERCENT = new BigDecimal("30");
""",
        "pre_write": "        validateDiscount(dto);\n",
        "service": """
    private void validateDiscount(PromotionCampaignDto dto) {
        if (dto.discountPercent().signum() <= 0 || dto.discountPercent().compareTo(MAX_DISCOUNT_PERCENT) > 0) {
            throw new BusinessRuleException("INVALID_CAMPAIGN_DISCOUNT",
                    "Campaign discount must be greater than 0 and at most " + MAX_DISCOUNT_PERCENT + "%");
        }
        if (dto.startsAt() != null && dto.endsAt() != null && !dto.endsAt().isAfter(dto.startsAt())) {
            throw new BusinessRuleException("INVALID_CAMPAIGN_PERIOD", "Campaign must end after it starts");
        }
    }
""",
    },
    "code_redeem": {
        "service_imports": ["com.example.shop.common.error.BusinessRuleException"],
        "service": """
    @Transactional
    public PromotionCodeDto redeem(String code) {
        int updated = jdbc.sql("UPDATE promotion_codes SET redemptions = COALESCE(redemptions, 0) + 1, updated_at = now() "
                        + "WHERE code = :code AND (max_redemptions IS NULL OR COALESCE(redemptions, 0) < max_redemptions)")
                .param("code", code)
                .update();
        if (updated == 0) {
            throw new BusinessRuleException("PROMOTION_CODE_EXHAUSTED", "Promotion code " + code + " is unknown or fully redeemed");
        }
        log.info("Promotion code redeemed code={}", code);
        return jdbc.sql(SELECT + " WHERE code = :code").param("code", code).query(mapper).single();
    }
""",
        "controller": """
    @PostMapping("/redemptions")
    @PreAuthorize("hasRole('USER')")
    public PromotionCodeDto redeem(@RequestParam String code) {
        return service.redeem(code);
    }
""",
    },
    "review_approve": {
        "service_imports": ["org.springframework.transaction.annotation.Transactional"],
        "service": """
    @Transactional
    public ProductReviewDto approve(Long id) {
        int updated = jdbc.sql("UPDATE product_reviews SET approved = TRUE, updated_at = now() WHERE id = :id AND approved IS NOT TRUE")
                .param("id", id)
                .update();
        if (updated == 0) {
            return get(id);
        }
        ProductReviewDto review = get(id);
        jdbc.sql("UPDATE review_summaries SET review_count = COALESCE(review_count, 0) + 1, last_review_at = now(), "
                        + "updated_at = now() WHERE product_id = :productId")
                .param("productId", review.productId())
                .update();
        log.info("Review approved reviewId={} productId={}", id, review.productId());
        return review;
    }
""",
        "controller": """
    @PostMapping("/{id}/approval")
    @PreAuthorize("hasRole('SUPPORT')")
    public ProductReviewDto approve(@PathVariable Long id) {
        return service.approve(id);
    }
""",
    },
    "vote_upsert": {
        "service": """
    public ReviewVoteDto vote(Long reviewId, Long voterId, boolean helpful) {
        Long id = jdbc.sql("INSERT INTO review_votes (review_id, voter_id, helpful) VALUES (:reviewId, :voterId, :helpful) "
                        + "ON CONFLICT (review_id, voter_id) DO UPDATE SET helpful = EXCLUDED.helpful, updated_at = now() RETURNING id")
                .param("reviewId", reviewId)
                .param("voterId", voterId)
                .param("helpful", helpful)
                .query(Long.class)
                .single();
        return get(id);
    }
""",
        "controller_imports": ["com.example.shop.security.AuthenticatedUser",
                               "org.springframework.security.core.annotation.AuthenticationPrincipal"],
        "controller": """
    @PostMapping("/reviews/{reviewId}")
    @PreAuthorize("hasRole('USER')")
    public ReviewVoteDto vote(@PathVariable Long reviewId, @RequestParam boolean helpful,
                              @AuthenticationPrincipal AuthenticatedUser user) {
        return service.vote(reviewId, user.id(), helpful);
    }
""",
    },
    "redirect_resolve": {
        "service_imports": ["java.util.Optional", UTIL + ".Texts"],
        "service": """
    public Optional<String> resolve(String query) {
        String normalized = Texts.trimToNull(query);
        if (normalized == null) {
            return Optional.empty();
        }
        return jdbc.sql("SELECT target_url FROM search_redirects WHERE lower(query) = lower(:query) AND active = TRUE")
                .param("query", normalized)
                .query(String.class)
                .optional();
    }
""",
        "controller_imports": ["org.springframework.http.ResponseEntity"],
        "controller": """
    @GetMapping("/resolve")
    public ResponseEntity<String> resolve(@RequestParam("q") String query) {
        return service.resolve(query).map(ResponseEntity::ok).orElseGet(() -> ResponseEntity.notFound().build());
    }
""",
    },
    "rate_quote": {
        "service_imports": ["com.example.shop.common.error.BusinessRuleException"],
        "service": """
    public ShippingRateDto quote(Long methodId, Long zoneId, int weightGrams) {
        if (weightGrams <= 0) {
            throw new BusinessRuleException("INVALID_WEIGHT", "Weight must be positive");
        }
        return jdbc.sql(SELECT + " WHERE method_id = :methodId AND zone_id = :zoneId AND max_weight_grams >= :weight "
                        + "ORDER BY max_weight_grams LIMIT 1")
                .param("methodId", methodId)
                .param("zoneId", zoneId)
                .param("weight", weightGrams)
                .query(mapper)
                .optional()
                .orElseThrow(() -> new BusinessRuleException("NO_SHIPPING_RATE",
                        "No rate for method " + methodId + " in zone " + zoneId + " up to " + weightGrams + " g"));
    }
""",
        "controller": """
    @GetMapping("/quote")
    public ShippingRateDto quote(@RequestParam Long methodId, @RequestParam Long zoneId, @RequestParam int weightGrams) {
        return service.quote(methodId, zoneId, weightGrams);
    }
""",
    },
}


# ---------------------------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------------------------
def gen_service(e):
    x = EXTRAS.get(e.extra, {})
    imports = {"com.example.shop.common.error.ResourceNotFoundException", "java.util.List",
               "org.slf4j.Logger", "org.slf4j.LoggerFactory",
               "org.springframework.jdbc.core.simple.JdbcClient", "org.springframework.stereotype.Service"}
    imports.update(x.get("service_imports", []))
    cols = ["id"] + [f.column for f in e.fields]
    ins_cols = [f.column for f in e.fields]
    ins_vals = [":" + f.name for f in e.fields]
    pre = x.get("pre_write", "")
    tx = "    @Transactional\n" if e.tx else ""
    where_active = " WHERE active = TRUE" if e.soft else ""
    if e.tx or e.owned or "@Transactional" in x.get("service", ""):
        imports.add("org.springframework.transaction.annotation.Transactional")
    n, d = e.name, e.dto
    methods = []

    if e.owned:
        imports.update(["com.example.shop.common.error.ForbiddenOperationException", "java.util.Map"])
        methods.append(f"""
    public List<{d}> list(Long userId, int page, int size) {{
        int limit = Math.min(Math.max(size, 1), MAX_PAGE_SIZE);
        return jdbc.sql(SELECT + " WHERE user_id = :userId ORDER BY {e.order} LIMIT :limit OFFSET :offset")
                .param("userId", userId)
                .param("limit", limit)
                .param("offset", (long) Math.max(page, 0) * limit)
                .query(mapper)
                .list();
    }}

    public {d} get(Long id, Long userId) {{
        return jdbc.sql(SELECT + " WHERE id = :id AND user_id = :userId")
                .param("id", id)
                .param("userId", userId)
                .query(mapper)
                .optional()
                .orElseThrow(() -> new ResourceNotFoundException("{n}", id));
    }}

{tx}    public {d} create(Long userId, {d} dto) {{
        Map<String, Object> params = mapper.toParams(dto);
        params.put("userId", userId);
        Long id = jdbc.sql("INSERT INTO {e.table} (user_id, {', '.join(ins_cols)}) VALUES (:userId, {', '.join(ins_vals)}) RETURNING id")
                .params(params)
                .query(Long.class)
                .single();
        log.info("{n} created id={{}} userId={{}}", id, userId);
        return get(id, userId);
    }}

    @Transactional
    public void delete(Long id, Long currentUserId) {{
        Long ownerId = jdbc.sql("SELECT user_id FROM {e.table} WHERE id = :id")
                .param("id", id)
                .query(Long.class)
                .optional()
                .orElseThrow(() -> new ResourceNotFoundException("{n}", id));
        if (!ownerId.equals(currentUserId)) {{
            throw new ForbiddenOperationException("{n} " + id + " belongs to another user");
        }}
        jdbc.sql("DELETE FROM {e.table} WHERE id = :id").param("id", id).update();
        log.info("{n} deleted id={{}} userId={{}}", id, currentUserId);
    }}
""")
    else:
        methods.append(f"""
    public List<{d}> list(int page, int size) {{
        int limit = Math.min(Math.max(size, 1), MAX_PAGE_SIZE);
        return jdbc.sql(SELECT + "{where_active} ORDER BY {e.order} LIMIT :limit OFFSET :offset")
                .param("limit", limit)
                .param("offset", (long) Math.max(page, 0) * limit)
                .query(mapper)
                .list();
    }}
""")
        if e.search:
            imports.add(UTIL + ".Texts")
            and_active = " AND active = TRUE" if e.soft else ""
            methods.append(f"""
    public List<{d}> search(String query, int size) {{
        String term = Texts.trimToNull(query);
        if (term == null) {{
            return List.of();
        }}
        return jdbc.sql(SELECT + " WHERE {e.search} ILIKE :term{and_active} ORDER BY {e.search} LIMIT :limit")
                .param("term", "%" + term.replace("%", "\\\\%").replace("_", "\\\\_") + "%")
                .param("limit", Math.min(Math.max(size, 1), MAX_PAGE_SIZE))
                .query(mapper)
                .list();
    }}
""")
        sets = ", ".join(f"{f.column} = :{f.name}" for f in e.fields)
        methods.append(f"""
    public {d} get(Long id) {{
        return jdbc.sql(SELECT + " WHERE id = :id")
                .param("id", id)
                .query(mapper)
                .optional()
                .orElseThrow(() -> new ResourceNotFoundException("{n}", id));
    }}

{tx}    public {d} create({d} dto) {{
{pre}        Long id = jdbc.sql("INSERT INTO {e.table} ({', '.join(ins_cols)}) VALUES ({', '.join(ins_vals)}) RETURNING id")
                .params(mapper.toParams(dto))
                .query(Long.class)
                .single();
        log.info("{n} created id={{}}", id);
        return get(id);
    }}

{tx}    public {d} update(Long id, {d} dto) {{
{pre}        int updated = jdbc.sql("UPDATE {e.table} SET {sets}, updated_at = now() WHERE id = :id")
                .params(mapper.toParams(dto))
                .param("id", id)
                .update();
        if (updated == 0) {{
            throw new ResourceNotFoundException("{n}", id);
        }}
        log.info("{n} updated id={{}}", id);
        return get(id);
    }}
""")
        if e.soft:
            methods.append(f"""
{tx}    public void deactivate(Long id) {{
        int updated = jdbc.sql("UPDATE {e.table} SET active = FALSE, updated_at = now() WHERE id = :id AND active = TRUE")
                .param("id", id)
                .update();
        if (updated == 0) {{
            throw new ResourceNotFoundException("{n}", id);
        }}
        log.info("{n} deactivated id={{}}", id);
    }}
""")
        else:
            methods.append(f"""
{tx}    public void delete(Long id) {{
        int deleted = jdbc.sql("DELETE FROM {e.table} WHERE id = :id").param("id", id).update();
        if (deleted == 0) {{
            throw new ResourceNotFoundException("{n}", id);
        }}
        log.info("{n} deleted id={{}}", id);
    }}
""")
    methods.append(x.get("service", ""))
    constants = x.get("constants", "")
    owner_doc = " All operations are scoped to the calling user." if e.owned else ""
    return f"""package {e.pkg};

{imports_block(imports)}

/** Management of {e.label} records ({{@code {e.table}}}).{owner_doc} */
@Service
public class {n}Service {{

    private static final Logger log = LoggerFactory.getLogger({n}Service.class);
    private static final int MAX_PAGE_SIZE = {e.max_page};
    private static final String SELECT = "SELECT {', '.join(cols)} FROM {e.table}";
{constants}
    private final JdbcClient jdbc;
    private final {n}Mapper mapper;

    public {n}Service(JdbcClient jdbc, {n}Mapper mapper) {{
        this.jdbc = jdbc;
        this.mapper = mapper;
    }}
{"".join(methods)}}}
"""


# ---------------------------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------------------------
def gen_controller(e):
    x = EXTRAS.get(e.extra, {})
    w = "org.springframework.web.bind.annotation."
    imports = {"java.util.List", "org.slf4j.Logger", "org.slf4j.LoggerFactory",
               "org.springframework.http.HttpStatus", "org.springframework.security.access.prepost.PreAuthorize",
               w + "DeleteMapping", w + "GetMapping", w + "PathVariable", w + "PostMapping", w + "RequestBody",
               w + "RequestMapping", w + "RequestParam", w + "ResponseStatus", w + "RestController",
               "jakarta.validation.Valid"}
    imports.update(x.get("controller_imports", []))
    n, d = e.name, e.dto
    default_size = min(20, e.max_page)
    plural = e.path.replace("-", " ")
    if e.owned:
        imports.update(["com.example.shop.security.AuthenticatedUser",
                        "org.springframework.security.core.annotation.AuthenticationPrincipal"])
        base = "/api/me/" + e.path
        body = f"""
    @GetMapping
    @PreAuthorize("hasRole('USER')")
    public List<{d}> list(@AuthenticationPrincipal AuthenticatedUser user,
                          @RequestParam(defaultValue = "0") int page,
                          @RequestParam(defaultValue = "{default_size}") int size) {{
        log.debug("List {plural} userId={{}} page={{}} size={{}}", user.id(), page, size);
        return service.list(user.id(), page, size);
    }}

    @GetMapping("/{{id}}")
    @PreAuthorize("hasRole('USER')")
    public {d} get(@PathVariable Long id, @AuthenticationPrincipal AuthenticatedUser user) {{
        return service.get(id, user.id());
    }}

    @PostMapping
    @PreAuthorize("hasRole('USER')")
    @ResponseStatus(HttpStatus.CREATED)
    public {d} create(@Valid @RequestBody {d} dto, @AuthenticationPrincipal AuthenticatedUser user) {{
        return service.create(user.id(), dto);
    }}

    @DeleteMapping("/{{id}}")
    @PreAuthorize("hasRole('USER')")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id, @AuthenticationPrincipal AuthenticatedUser user) {{
        service.delete(id, user.id());
    }}
"""
    else:
        imports.add(w + "PutMapping")
        base = "/api/catalog/" + e.path
        search = ""
        if e.search:
            search = f"""
    @GetMapping("/search")
    public List<{d}> search(@RequestParam("q") String query, @RequestParam(defaultValue = "10") int size) {{
        return service.search(query, size);
    }}
"""
        remove = "deactivate" if e.soft else "delete"
        body = f"""
    @GetMapping
    public List<{d}> list(@RequestParam(defaultValue = "0") int page,
                          @RequestParam(defaultValue = "{default_size}") int size) {{
        log.debug("List {plural} page={{}} size={{}}", page, size);
        return service.list(page, size);
    }}
{search}
    @GetMapping("/{{id}}")
    public {d} get(@PathVariable Long id) {{
        return service.get(id);
    }}

    @PostMapping
    @PreAuthorize("hasRole('{e.role}')")
    @ResponseStatus(HttpStatus.CREATED)
    public {d} create(@Valid @RequestBody {d} dto) {{
        return service.create(dto);
    }}

    @PutMapping("/{{id}}")
    @PreAuthorize("hasRole('{e.role}')")
    public {d} update(@PathVariable Long id, @Valid @RequestBody {d} dto) {{
        return service.update(id, dto);
    }}

    @DeleteMapping("/{{id}}")
    @PreAuthorize("hasRole('{e.role}')")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void {remove}(@PathVariable Long id) {{
        log.info("{n} {remove} requested id={{}}", id);
        service.{remove}(id);
    }}
"""
    if "PutMapping" in x.get("controller", ""):
        imports.add(w + "PutMapping")
    body += x.get("controller", "")
    return f"""package {e.pkg};

{imports_block(imports)}

@RestController
@RequestMapping("{base}")
public class {n}Controller {{

    private static final Logger log = LoggerFactory.getLogger({n}Controller.class);

    private final {n}Service service;

    public {n}Controller({n}Service service) {{
        this.service = service;
    }}
{body}}}
"""


# ---------------------------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------------------------
def gen_migration():
    out = ["-- Catalogue read models (attributes, brands, bundles, collections, inventory, media,",
           "-- pricing, promotions, reviews, search tuning, shipping, wishlists).", ""]
    for e in ENTS:
        cols = ["    id BIGSERIAL PRIMARY KEY"]
        if e.owned:
            cols.append("    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE")
        for f in e.fields:
            sql = "VARCHAR(%d)" % f.max if f.kind == "S" else SQL_TYPES[f.kind]
            extra = " NOT NULL" if f.required else ""
            if f.slug:
                extra += " UNIQUE"
            cols.append(f"    {f.column} {sql}{extra}")
        if e.soft:
            cols.append("    active BOOLEAN NOT NULL DEFAULT TRUE")
        cols.append("    created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
        cols.append("    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
        if "unique" in e.feat:
            uc = e.feat["unique"]
            cols.append(f"    CONSTRAINT uq_{e.table}_{uc.replace(',', '_')} UNIQUE ({uc.replace(',', ', ')})")
        out.append(f"CREATE TABLE {e.table} (")
        out.append(",\n".join(cols))
        out.append(");")
        if e.owned:
            out.append(f"CREATE INDEX idx_{e.table}_user ON {e.table} (user_id);")
        out.append("")
    path = os.path.join(TARGET, "src/main/resources/db/migration/V3__catalog_read_models.sql")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def main():
    for e in ENTS:
        write(e.pkg, e.dto, gen_dto(e))
        write(e.pkg, e.name + "Mapper", gen_mapper(e))
        write(e.pkg, e.name + "Service", gen_service(e))
        write(e.pkg, e.name + "Controller", gen_controller(e))
    gen_migration()


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("usage: prepare.py <target-dir>")
    TARGET = sys.argv[1]
    main()

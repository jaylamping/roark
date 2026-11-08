//! Reading YAML nodes into typed values, collecting every problem rather than stopping at the first.

use crate::error::{Problem, ProblemKind};
use crate::yaml::{Entry, Node, Value};

/// Collects problems while the loader walks the tree.
#[derive(Default)]
pub(crate) struct Reader {
    pub(crate) problems: Vec<Problem>,
}

/// The keys of one mapping. Each key is taken once; `finish` reports the ones nobody took.
pub(crate) struct Fields<'n> {
    entries: &'n [Entry],
    taken: Vec<bool>,
    pub(crate) path: String,
    pub(crate) line: usize,
}

impl Reader {
    pub(crate) fn report(&mut self, line: usize, path: impl Into<String>, kind: ProblemKind) {
        self.problems.push(Problem {
            line,
            path: path.into(),
            kind,
        });
    }

    /// The node as a mapping, or a reported problem.
    pub(crate) fn fields<'n>(&mut self, node: &'n Node, path: &str) -> Option<Fields<'n>> {
        match &node.value {
            Value::Map(entries) => Some(Fields {
                entries,
                taken: vec![false; entries.len()],
                path: path.to_owned(),
                line: node.line,
            }),
            Value::Scalar { .. } | Value::Seq(_) => {
                self.report(node.line, path, ProblemKind::Expected("a mapping"));
                None
            }
        }
    }

    /// A required field. Missing or unparsable is reported and gives `None`.
    pub(crate) fn required<T>(
        &mut self,
        fields: &mut Fields<'_>,
        key: &str,
        parse: impl FnOnce(&Node) -> Result<T, ProblemKind>,
    ) -> Option<T> {
        let node = fields.take(key, self)?;
        self.parsed(node, fields.path_of(key), parse)
    }

    /// A field that must be written out but may be `null`. The outer `None` means a problem was reported.
    #[expect(
        clippy::option_option,
        reason = "outer None is a reported problem, inner None is a written `null`"
    )]
    pub(crate) fn nullable<T>(
        &mut self,
        fields: &mut Fields<'_>,
        key: &str,
        parse: impl FnOnce(&Node) -> Result<T, ProblemKind>,
    ) -> Option<Option<T>> {
        let node = fields.take(key, self)?;
        if is_null(node) {
            return Some(None);
        }
        self.parsed(node, fields.path_of(key), parse).map(Some)
    }

    pub(crate) fn parsed<T>(
        &mut self,
        node: &Node,
        path: String,
        parse: impl FnOnce(&Node) -> Result<T, ProblemKind>,
    ) -> Option<T> {
        parse(node)
            .map_err(|kind| self.report(node.line, path, kind))
            .ok()
    }
}

impl<'n> Fields<'n> {
    /// The value under `key`, reporting it missing if absent.
    pub(crate) fn take(&mut self, key: &str, reader: &mut Reader) -> Option<&'n Node> {
        let found = self.entries.iter().position(|e| e.key == key);
        if let Some(i) = found {
            if let Some(t) = self.taken.get_mut(i) {
                *t = true;
            }
        } else {
            reader.report(
                self.line,
                self.path.clone(),
                ProblemKind::Missing(key.to_owned()),
            );
        }
        found.and_then(|i| self.entries.get(i)).map(|e| &e.value)
    }

    /// Every entry, marking them all taken, for mappings keyed by name (buses, limbs).
    pub(crate) fn all(&mut self) -> &'n [Entry] {
        self.taken.fill(true);
        self.entries
    }

    pub(crate) fn has(&self, key: &str) -> bool {
        self.entries.iter().any(|e| e.key == key)
    }

    /// The line of `key`'s value, so a problem with a field points at that field; the mapping's line if it's absent.
    pub(crate) fn line_of(&self, key: &str) -> usize {
        self.entries
            .iter()
            .find(|e| e.key == key)
            .map_or(self.line, |e| e.value.line)
    }

    pub(crate) fn path_of(&self, key: &str) -> String {
        if self.path.is_empty() {
            key.to_owned()
        } else {
            format!("{}.{key}", self.path)
        }
    }

    /// Reports every key nobody asked for.
    pub(crate) fn finish(self, reader: &mut Reader) {
        for (entry, taken) in self.entries.iter().zip(&self.taken) {
            if !taken {
                reader.report(
                    entry.key_line,
                    self.path.clone(),
                    ProblemKind::UnknownKey(entry.key.clone()),
                );
            }
        }
    }
}

/// Plain `null` or `~`. An empty value is not null: unknown values are written out (skeleton.md section 3).
pub(crate) fn is_null(node: &Node) -> bool {
    matches!(&node.value, Value::Scalar { text, quoted: false } if text == "null" || text == "~")
}

/// A scalar's non-blank text. An empty value, or another spelling of null (`Null`, `NULL`), is refused rather than
/// read as text, so a blank can't stand in for a value ("Null is not permission", PLAN item 1).
pub(crate) fn text(node: &Node) -> Result<&str, ProblemKind> {
    match &node.value {
        Value::Scalar {
            text,
            quoted: false,
        } if matches!(text.as_str(), "Null" | "NULL") => {
            Err(ProblemKind::Expected("`null` in lower case"))
        }
        Value::Scalar { text, .. } if !is_null(node) && !text.trim().is_empty() => Ok(text),
        Value::Scalar { .. } | Value::Seq(_) | Value::Map(_) => Err(ProblemKind::Expected(
            "text (write `null` if it isn't known yet)",
        )),
    }
}

/// A plain (unquoted) scalar's text: numbers and signs are never written as quoted strings.
pub(crate) fn plain(node: &Node) -> Option<&str> {
    match &node.value {
        Value::Scalar {
            text,
            quoted: false,
        } => Some(text),
        Value::Scalar { quoted: true, .. } | Value::Seq(_) | Value::Map(_) => None,
    }
}

/// A finite number written as a plain scalar.
pub(crate) fn number(node: &Node) -> Result<f64, ProblemKind> {
    let text = plain(node).ok_or(ProblemKind::Expected("a number"))?;
    let lower = text.to_ascii_lowercase();
    if matches!(
        lower.trim_start_matches(['+', '-']),
        ".nan" | ".inf" | "nan" | "inf" | "infinity"
    ) {
        return Err(ProblemKind::NonFinite);
    }
    // As in `integer`: YAML 1.1 tools read `012` as octal 10. `0`, `0.5` and `-0.5` keep their single zero.
    let whole = lower
        .trim_start_matches(['+', '-'])
        .split(['.', 'e'])
        .next()
        .unwrap_or_default();
    if whole.len() > 1 && whole.starts_with('0') {
        return Err(ProblemKind::Expected("a number without leading zeros"));
    }
    let value: f64 = text
        .parse()
        .map_err(|_| ProblemKind::Expected("a number"))?;
    if value.is_finite() {
        Ok(value)
    } else {
        Err(ProblemKind::NonFinite)
    }
}

/// A non-negative integer in plain decimal digits. A leading zero is refused: YAML 1.1 tools read `012` as octal 10.
pub(crate) fn integer(node: &Node) -> Result<u64, ProblemKind> {
    match plain(node) {
        Some(text)
            if !text.is_empty()
                && text.bytes().all(|b| b.is_ascii_digit())
                && (text == "0" || !text.starts_with('0')) =>
        {
            text.parse()
                .map_err(|_| ProblemKind::OutOfRange("below 2^64"))
        }
        Some(_) | None => Err(ProblemKind::Expected(
            "a whole number without leading zeros",
        )),
    }
}

/// A finite number above zero, through the unit's constructor.
pub(crate) fn positive<T>(make: fn(f64) -> Option<T>) -> impl Fn(&Node) -> Result<T, ProblemKind> {
    move |node| {
        let value = number(node)?;
        if value > 0.0 {
            make(value).ok_or(ProblemKind::NonFinite)
        } else {
            Err(ProblemKind::OutOfRange("above 0"))
        }
    }
}

/// `[lower, upper]`: two finite numbers, lower below upper.
pub(crate) fn range<T>(
    make: fn(f64) -> Option<T>,
) -> impl Fn(&Node) -> Result<(T, T), ProblemKind> {
    move |node| {
        let Value::Seq(items) = &node.value else {
            return Err(ProblemKind::Expected("[lower, upper]"));
        };
        let [lower, upper] = items.as_slice() else {
            return Err(ProblemKind::Expected("[lower, upper]"));
        };
        let (lower, upper) = (number(lower)?, number(upper)?);
        if lower >= upper {
            return Err(ProblemKind::ReversedRange);
        }
        make(lower).zip(make(upper)).ok_or(ProblemKind::NonFinite)
    }
}

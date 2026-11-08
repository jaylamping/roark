//! A small YAML tree with line numbers, built from `saphyr-parser` events.
//!
//! The skeleton is plain YAML (skeleton.md section 4): no anchors, aliases, merge keys or tags, one document, string keys.
//! Building our own tree from parser events lets us refuse those at the line they appear, and keep every node's line so
//! each problem can point at it. Scalars are kept as text; `read` decides what each field's text means.

use saphyr_parser::{Event, Parser, ScalarStyle};

use crate::error::{Problem, ProblemKind};

/// Deeper than any skeleton needs (root, limbs, limb, joints, joint, range is six). A bound so a hostile file can't
/// grow the stack without limit (rust.md section 4).
const MAX_DEPTH: usize = 16;

/// One YAML node and the line (1-based) it starts on.
#[derive(Debug)]
pub(crate) struct Node {
    pub(crate) line: usize,
    pub(crate) value: Value,
}

#[derive(Debug)]
pub(crate) enum Value {
    /// `quoted` is true for single- or double-quoted scalars, which are always strings.
    Scalar {
        text: String,
        quoted: bool,
    },
    Seq(Vec<Node>),
    Map(Vec<Entry>),
}

#[derive(Debug)]
pub(crate) struct Entry {
    pub(crate) key: String,
    pub(crate) key_line: usize,
    pub(crate) value: Node,
}

enum Frame {
    Seq {
        line: usize,
        items: Vec<Node>,
    },
    Map {
        line: usize,
        entries: Vec<Entry>,
        key: Option<(String, usize)>,
    },
}

/// Parses `text` into one tree, or returns the first problem the parser or the plain-YAML rules found. Structural
/// problems stop the parse, because nothing after them can be trusted.
pub(crate) fn parse(text: &str) -> Result<Node, Problem> {
    let mut stack: Vec<Frame> = Vec::new();
    let mut root: Option<Node> = None;
    let mut documents = 0_usize;

    for item in Parser::new_from_str(text) {
        let (event, span) = item.map_err(|e| {
            Problem::at_line(e.marker().line(), ProblemKind::Yaml(e.info().to_owned()))
        })?;
        let line = span.start.line();
        let plain_rule =
            |what: &str| Problem::at_line(line, ProblemKind::NotPlainYaml(what.to_owned()));
        let node = match event {
            Event::StreamStart | Event::StreamEnd | Event::DocumentEnd | Event::Nothing => continue,
            Event::DocumentStart(_) => {
                documents += 1;
                if documents > 1 {
                    return Err(plain_rule("more than one document"));
                }
                continue;
            }
            Event::Alias(_) => return Err(plain_rule("alias")),
            Event::Scalar(text, style, anchor, tag) => {
                if anchor != 0 {
                    return Err(plain_rule("anchor"));
                }
                if tag.is_some() {
                    return Err(plain_rule("tag"));
                }
                let quoted = match style {
                    ScalarStyle::SingleQuoted | ScalarStyle::DoubleQuoted => true,
                    ScalarStyle::Plain => false,
                    ScalarStyle::Literal | ScalarStyle::Folded => {
                        return Err(plain_rule("block scalar"));
                    }
                };
                Node {
                    line,
                    value: Value::Scalar {
                        text: text.into_owned(),
                        quoted,
                    },
                }
            }
            Event::SequenceStart(anchor, ref tag) | Event::MappingStart(anchor, ref tag) => {
                if anchor != 0 {
                    return Err(plain_rule("anchor"));
                }
                if tag.is_some() {
                    return Err(plain_rule("tag"));
                }
                if let Some(Frame::Map { key: None, .. }) = stack.last() {
                    return Err(plain_rule("non-scalar mapping key"));
                }
                if stack.len() >= MAX_DEPTH {
                    return Err(plain_rule("nesting deeper than the skeleton needs"));
                }
                stack.push(if matches!(event, Event::SequenceStart(..)) {
                    Frame::Seq {
                        line,
                        items: Vec::new(),
                    }
                } else {
                    Frame::Map {
                        line,
                        entries: Vec::new(),
                        key: None,
                    }
                });
                continue;
            }
            Event::SequenceEnd | Event::MappingEnd => match stack.pop() {
                Some(Frame::Seq { line, items }) => Node {
                    line,
                    value: Value::Seq(items),
                },
                Some(Frame::Map {
                    line,
                    entries,
                    key: None,
                }) => Node {
                    line,
                    value: Value::Map(entries),
                },
                Some(Frame::Map { key: Some(_), .. }) | None => {
                    return Err(Problem::at_line(
                        line,
                        ProblemKind::Yaml("unbalanced document".to_owned()),
                    ));
                }
            },
        };
        attach(&mut stack, &mut root, node)?;
    }
    root.ok_or_else(|| Problem::at_line(1, ProblemKind::Yaml("the file is empty".to_owned())))
}

/// Puts a finished node into its parent: as a key, as a value under the pending key, or as a sequence item.
fn attach(stack: &mut [Frame], root: &mut Option<Node>, node: Node) -> Result<(), Problem> {
    match stack.last_mut() {
        None => *root = Some(node),
        Some(Frame::Seq { items, .. }) => items.push(node),
        Some(Frame::Map { entries, key, .. }) => {
            if let Some((key, key_line)) = key.take() {
                entries.push(Entry {
                    key,
                    key_line,
                    value: node,
                });
                return Ok(());
            }
            let Value::Scalar { text, .. } = node.value else {
                return Err(Problem::at_line(
                    node.line,
                    ProblemKind::NotPlainYaml("non-scalar mapping key".to_owned()),
                ));
            };
            if text == "<<" {
                return Err(Problem::at_line(
                    node.line,
                    ProblemKind::NotPlainYaml("merge key".to_owned()),
                ));
            }
            if entries.iter().any(|e| e.key == text) {
                return Err(Problem::at_line(node.line, ProblemKind::DuplicateKey(text)));
            }
            *key = Some((text, node.line));
        }
    }
    Ok(())
}

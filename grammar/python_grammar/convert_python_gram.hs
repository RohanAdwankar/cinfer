{-# LANGUAGE OverloadedStrings #-}

-- Convert CPython's PEG grammar (python.gram) into a best-effort GBNF grammar.
-- Usage:
--   runghc convert_python_gram.hs python.gram Tokens python.gbnf
--
-- Notes:
-- - This is a lossy conversion: PEG lookahead (&, !, &&), commit (~), and
--   semantic actions are removed. This will over-generate.
-- - Indentation-sensitive constructs cannot be represented faithfully in GBNF.
--   INDENT/DEDENT are approximated with whitespace patterns.
-- - Token rules (NAME/NUMBER/STRING/...) are approximations and should be
--   refined for tighter validation if needed.

module Main (main) where

import Data.Char (isAlpha, isAlphaNum, isSpace, toLower, toUpper)
import Data.List (intercalate, isInfixOf, isPrefixOf)
import qualified Data.Map.Strict as Map
import qualified Data.Set as Set
import System.Environment (getArgs)
import System.Exit (die)

-- Token representation for simple transformations
newtype Tok = Tok { unTok :: String } deriving (Eq, Show)

main :: IO ()
main = do
    args <- getArgs
    case args of
        [gramPath, tokensPath, outPath] -> do
            tokensText <- readFile tokensPath
            gramText <- readFile gramPath
            let (literalMap, allTokens) = parseTokens tokensText
            let gramLines = lines gramText
            let filtered = stripTrailer gramLines
            let ruleNames = collectRuleNames filtered
            let ruleMap = Map.fromList [(r, toGbnfName r) | r <- ruleNames]
            let (converted, usedTokens) = convertLines ruleMap literalMap filtered
            let tokenRules = buildTokenRules literalMap allTokens usedTokens
            let header = [
                    "# Auto-generated from python.gram. Best-effort conversion.",
                    "# Lossy: PEG lookaheads and actions removed; indentation approximated.",
                    "root ::= file"
                    ]
            writeFile outPath (unlines (header ++ converted ++ tokenRules))
        _ -> die "Usage: runghc convert_python_gram.hs python.gram Tokens python.gbnf"

-- -----------------------------
-- Parsing helpers
-- -----------------------------

stripTrailer :: [String] -> [String]
stripTrailer = go False
  where
    go _ [] = []
    go inTrailer (l:ls)
        | not inTrailer && "@trailer" `isPrefixOf` dropWhile isSpace l = go True ls
        | inTrailer && "'''" `isInfixOf` l = go False ls
        | inTrailer = go True ls
        | otherwise = l : go False ls

collectRuleNames :: [String] -> [String]
collectRuleNames = foldr collect []
  where
    collect line acc =
        case parseHeaderName (stripComment line) of
            Just name -> name : acc
            Nothing -> acc

parseHeaderName :: String -> Maybe String
parseHeaderName line =
    let s = dropWhile isSpace line
    in case s of
        ('|':_) -> Nothing
        _ ->
            case break (== ':') s of
                (lhs, _:_) ->
                    case span isIdentChar lhs of
                        (name, _rest) | not (null name) -> Just name
                        _ -> Nothing
                _ -> Nothing

isIdentChar :: Char -> Bool
isIdentChar c = isAlphaNum c || c == '_'

stripComment :: String -> String
stripComment = go False False
  where
    go _ _ [] = []
    go inS inD (c:cs)
        | c == '\\' = c : case cs of
            [] -> []
            (n:ns) -> n : go inS inD ns
        | c == '\'' && not inD = c : go (not inS) inD cs
        | c == '"' && not inS = c : go inS (not inD) cs
        | c == '#' && not inS && not inD = []
        | otherwise = c : go inS inD cs

-- Remove semantic action blocks across lines
stripActions :: Int -> String -> (Int, String)
stripActions depth = go depth False False ""
    where
        go d _ _ acc [] = (d, reverse acc)
        go d inS inD acc (c:cs)
                | c == '\\' =
                        case cs of
                                [] -> (d, reverse (c:acc))
                                (n:ns) -> go d inS inD (n:c:acc) ns
                | c == '\'' && not inD = go d (not inS) inD (c:acc) cs
                | c == '"' && not inS = go d inS (not inD) (c:acc) cs
                | inS || inD = go d inS inD (c:acc) cs
                | c == '{' = go (d + 1) inS inD acc cs
                | c == '}' && d > 0 = go (d - 1) inS inD acc cs
                | d > 0 = go d inS inD acc cs
                | otherwise = go d inS inD (c:acc) cs

-- -----------------------------
-- Tokens and mapping
-- -----------------------------

parseTokens :: String -> (Map.Map String String, Set.Set String)
parseTokens content = foldr parseLine (Map.empty, Set.empty) (lines content)
  where
    parseLine line (litMap, tokens) =
        let s = dropWhile isSpace line
        in if null s || "#" `isPrefixOf` s
            then (litMap, tokens)
            else
                let name = takeWhile isIdentChar s
                    lit = extractLiteral s
                    tokens' = Set.insert name tokens
                in case lit of
                    Just v -> (Map.insert name v litMap, tokens')
                    Nothing -> (litMap, tokens)

extractLiteral :: String -> Maybe String
extractLiteral s =
    case dropWhile (/= '\'') s of
        [] -> Nothing
        (_:rest) ->
            let (lit, rest2) = span (/= '\'') rest
            in if null rest2 then Nothing else Just lit

toGbnfName :: String -> String
toGbnfName = map toLower . map repl
  where
    repl '_' = '-'
    repl c = c

-- -----------------------------
-- Conversion
-- -----------------------------

convertLines :: Map.Map String String -> Map.Map String String -> [String] -> ([String], Set.Set String)
convertLines ruleMap literalMap linesIn = finalize (collectRules linesIn)
  where
    finalize rules =
        let (acc, used) = foldl
                (\(acc, used) (name, parts) ->
                    if "invalid_" `isPrefixOf` name
                        then (acc, used)
                        else
                            let gbnfName = Map.findWithDefault (toGbnfName name) name ruleMap
                                expr = if gbnfName `Set.member` brokenRules
                                    then "fallback"
                                    else unwords (reverse parts)
                                (convertedExpr, used') = convertExpr ruleMap literalMap expr
                                finalExpr = if isLeftRecursive gbnfName convertedExpr
                                    then "fallback"
                                    else convertedExpr
                            in (acc ++ [gbnfName ++ " ::= " ++ finalExpr], Set.union used used')
                )
                ([], Set.empty)
                rules
            fallbackRule = "fallback ::= tok-name | tok-number | tok-string"
        in (acc ++ [fallbackRule], used)

    collectRules = go 0 Nothing []

    go _ current acc [] =
        case current of
            Just (name, parts) -> acc ++ [(name, parts)]
            Nothing -> acc
    go depth current acc (l:ls) =
        let (depth', noActions) = stripActions depth l
            noComment = stripComment noActions
            trimmed = dropWhile isSpace noComment
        in if null trimmed
            then go depth' current acc ls
            else case parseHeaderName noComment of
                Just name ->
                    let acc' = case current of
                            Just (n, parts) -> acc ++ [(n, parts)]
                            Nothing -> acc
                        expr = drop 1 (dropWhile (/= ':') noComment)
                    in go depth' (Just (name, [expr])) acc' ls
                Nothing ->
                    case current of
                        Just (n, parts) -> go depth' (Just (n, trimmed : parts)) acc ls
                        Nothing -> go depth' current acc ls

convertExpr :: Map.Map String String -> Map.Map String String -> String -> (String, Set.Set String)
convertExpr ruleMap literalMap expr =
    let toks = tokenize expr
        toks1 = dropLeadingPipes (stripLabelAssignments (dropLabels toks))
        toks2 = dropLookahead toks1
        toks3 = convertOptionalGroups toks2
        toks4 = convertSeparated toks3
        toks5 = sanitizeTokens toks4
        toks6 = cleanupPipes (dropInvalidRefs toks5)
        (toks7, usedTokens) = mapIdents ruleMap literalMap toks6
    in (renderTokens toks7, usedTokens)

-- Tokenize a grammar expression into simple tokens

tokenize :: String -> [Tok]
tokenize = go []
  where
    go acc [] = reverse acc
    go acc (c:cs)
        | isSpace c = go acc cs
        | c == '\'' || c == '"' =
            let (lit, rest) = spanString c cs
            in go (Tok (quoteToDouble c lit) : acc) rest
        | isIdentChar c =
            let (name, rest) = span isIdentChar (c:cs)
            in go (Tok name : acc) rest
        | c == '&' =
            case cs of
                ('&':rest) -> go (Tok "&&" : acc) rest
                _ -> go (Tok "&" : acc) cs
        | otherwise = go (Tok [c] : acc) cs

spanString :: Char -> String -> (String, String)
spanString quote = go []
  where
    go acc [] = (reverse acc, [])
    go acc (c:cs)
        | c == '\\' =
            case cs of
                [] -> (reverse (c:acc), [])
                (n:ns) -> go (n:c:acc) ns
        | c == quote = (reverse acc, cs)
        | otherwise = go (c:acc) cs

quoteToDouble :: Char -> String -> String
quoteToDouble _ content = '"' : escape content ++ "\""

escape :: String -> String
escape = concatMap esc
  where
    esc '"' = "\\\""
    esc '\\' = "\\\\"
    esc '\n' = "\\n"
    esc '\r' = "\\r"
    esc '\t' = "\\t"
    esc c = [c]

-- Remove label assignments like a= or a[Type]=

dropLabels :: [Tok] -> [Tok]
dropLabels [] = []
dropLabels (Tok name : rest)
    | isLabelName name =
        let (rest', hadType) = dropTypeAnnotation rest
        in case rest' of
            (Tok "=" : after) -> dropLabels after
            _ -> Tok name : (if hadType then rest else rest')
    | otherwise = Tok name : dropLabels rest


-- Drop [ ... ] type annotations immediately following a label

dropTypeAnnotation :: [Tok] -> ([Tok], Bool)
dropTypeAnnotation (Tok "[" : rest) = go 1 rest
  where
    go depth [] = ([], True)
    go depth (Tok "[" : xs) = go (depth + 1) xs
    go depth (Tok "]" : xs)
        | depth == 1 = (xs, True)
        | otherwise = go (depth - 1) xs
    go depth (_:xs) = go depth xs

dropTypeAnnotation ts = (ts, False)

-- Remove any remaining label assignments (label[Type]= or label=)

stripLabelAssignments :: [Tok] -> [Tok]
stripLabelAssignments [] = []
stripLabelAssignments (Tok name : Tok "[" : rest)
    | isLabelName name =
        let (inner, rest') = collect 1 [] rest
        in case rest' of
            (Tok "=" : after) -> stripLabelAssignments after
            _ -> Tok name : Tok "[" : inner ++ Tok "]" : stripLabelAssignments rest'
  where
    collect _ acc [] = (reverse acc, [])
    collect depth acc (Tok "[" : xs) = collect (depth + 1) (Tok "[" : acc) xs
    collect depth acc (Tok "]" : xs)
        | depth == 1 = (reverse acc, xs)
        | otherwise = collect (depth - 1) (Tok "]" : acc) xs
    collect depth acc (x:xs) = collect depth (x:acc) xs
stripLabelAssignments (Tok name : Tok "=" : rest)
    | isLabelName name = stripLabelAssignments rest
stripLabelAssignments (t:rest) = t : stripLabelAssignments rest

isLabelName :: String -> Bool
isLabelName n = not (null n) && isIdentChar (head n)

dropLeadingPipes :: [Tok] -> [Tok]
dropLeadingPipes (Tok "|" : rest) = dropLeadingPipes rest
dropLeadingPipes ts = ts

sanitizeTokens :: [Tok] -> [Tok]
sanitizeTokens = removeEmptyParens . trimUnclosed . dropStrayQuestion . dropExtraClose
  where
    dropExtraClose = go 0
    go _ [] = []
    go depth (t@(Tok tok):rest)
        | tok == "(" = t : go (depth + 1) rest
        | tok == ")" = if depth <= 0 then go depth rest else t : go (depth - 1) rest
        | otherwise = t : go depth rest

    dropStrayQuestion = goTok Nothing
    goTok _ [] = []
    goTok prev (t@(Tok tok):rest)
        | tok == "?" && isBadPrev prev = goTok prev rest
        | otherwise = t : goTok (Just tok) rest

    isBadPrev Nothing = True
    isBadPrev (Just p) = p == "(" || p == "|"

    trimUnclosed toks =
        let depth = countOpen toks
        in if depth <= 0 then toks else removeLastOpens depth (reverse toks)

    countOpen = foldl count 0
    count acc (Tok tok)
        | tok == "(" = acc + 1
        | tok == ")" = acc - 1
        | otherwise = acc

    removeLastOpens 0 rev = reverse rev
    removeLastOpens n [] = []
    removeLastOpens n (Tok tok:rest)
        | tok == "(" = removeLastOpens (n - 1) rest
        | otherwise = Tok tok : removeLastOpens n rest

    removeEmptyParens toks = go toks
      where
        go (Tok "(" : Tok ")" : rest) = go rest
        go (t:rest) = t : go rest
        go [] = []

dropInvalidRefs :: [Tok] -> [Tok]
dropInvalidRefs = filter (\(Tok t) -> not ("invalid-" `isPrefixOf` t))

cleanupPipes :: [Tok] -> [Tok]
cleanupPipes = dropTrailingPipes . dropLeadingPipes . collapsePipes
    where
        collapsePipes (Tok "|" : Tok "|" : rest) = collapsePipes (Tok "|" : rest)
        collapsePipes (t:rest) = t : collapsePipes rest
        collapsePipes [] = []

        dropTrailingPipes toks = reverse (dropWhile isPipe (reverse toks))
        isPipe (Tok "|") = True
        isPipe _ = False

isLeftRecursive :: String -> String -> Bool
isLeftRecursive name expr =
    let s = dropWhile isSpace expr
    in case s of
        _ | name `isPrefixOf` s && boundary (drop (length name) s) -> True
        '(' : rest ->
            let s2 = dropWhile isSpace rest
            in name `isPrefixOf` s2 && boundary (drop (length name) s2)
        _ -> False
  where
    boundary [] = True
    boundary (c:_) = not (isAlphaNum c) && c /= '-'

brokenRules :: Set.Set String
brokenRules = Set.fromList
    [ "assignment"
    , "raise-stmt"
    , "del-stmt"
    , "assert-stmt"
    , "import-stmt"
    , "import-from-targets"
    , "import-from-as-name"
    , "dotted-as-name"
    , "dotted-name"
    , "block"
    , "class-def-raw"
    , "function-def-raw"
    , "params"
    , "star-etc"
    , "kwds"
    , "default"
    , "if-stmt"
    , "elif-stmt"
    , "else-block"
    , "while-stmt"
    , "for-stmt"
    , "with-stmt"
    , "with-item"
    , "try-stmt"
    , "except-block"
    , "except-star-block"
    , "finally-block"
    , "match-stmt"
    , "case-block"
    , "as-pattern"
    , "mapping-pattern"
    , "class-pattern"
    , "type-params"
    , "type-param"
    , "expression"
    , "star-named-expression-sequence"
    , "named-expression"
    , "bitwise-or"
    , "bitwise-xor"
    , "bitwise-and"
    , "shift-expr"
    , "sum"
    , "term"
    , "primary"
    , "group"
    , "lambda-params"
    , "lambda-star-etc"
    , "lambda-kwds"
    , "fstring-replacement-field"
    , "tstring-format-spec-replacement-field"
    , "tstring-replacement-field"
    , "strings"
    , "dict"
    , "for-if-clause"
    , "listcomp"
    , "setcomp"
    , "genexp"
    , "arguments"
    , "starred-expression"
    , "kwarg-or-starred"
    , "kwarg-or-double-starred"
    , "t-primary"
    , "func-type-comment"
        ]

-- Drop PEG-specific operators not supported by GBNF

dropLookahead :: [Tok] -> [Tok]
dropLookahead = filter (\(Tok t) -> t /= "&" && t /= "!" && t /= "~" && t /= "&&")

-- Convert [ ... ] optional groups into ( ... ) ?

convertOptionalGroups :: [Tok] -> [Tok]
convertOptionalGroups = go []
  where
    go acc [] = reverse acc
    go acc (Tok "[" : rest) =
        let (inner, rest') = collect 1 [] rest
            convertedInner = convertOptionalGroups inner
        in go (Tok "?" : Tok ")" : convertedInner ++ Tok "(" : acc) rest'
    go acc (t:rest) = go (t:acc) rest

    collect _ acc [] = (reverse acc, [])
    collect depth acc (Tok "[" : xs) = collect (depth + 1) (Tok "[" : acc) xs
    collect depth acc (Tok "]" : xs)
        | depth == 1 = (reverse acc, xs)
        | otherwise = collect (depth - 1) (Tok "]" : acc) xs
    collect depth acc (x:xs) = collect depth (x:acc) xs

-- Convert s.e+ / s.e* into (e (s e)*) / (e (s e)*)?

convertSeparated :: [Tok] -> [Tok]
convertSeparated toks = go toks
  where
    go [] = []
    go ts =
        case parsePrimary ts of
            Nothing -> []
            Just (prim, rest) ->
                case rest of
                    (Tok "." : rest2) ->
                        case parsePrimary rest2 of
                            Just (elemTok, rest3) ->
                                case rest3 of
                                    (Tok "+" : rest4) ->
                                        prim ++ Tok "(" : elemTok ++ Tok "(" : prim ++ elemTok ++ Tok ")" : Tok "*" : Tok ")" : go rest4
                                    (Tok "*" : rest4) ->
                                        Tok "(" : elemTok ++ Tok "(" : prim ++ elemTok ++ Tok ")" : Tok "*" : Tok ")" : Tok "?" : go rest4
                                    _ -> prim ++ Tok "." : go rest
                            _ -> prim ++ Tok "." : go rest
                    _ -> prim ++ go rest

    parsePrimary [] = Nothing
    parsePrimary (Tok "(" : rest) =
        let (inner, rest') = collect 1 [] rest
        in Just (Tok "(" : inner ++ [Tok ")"], rest')
    parsePrimary (t:rest) = Just ([t], rest)

    collect _ acc [] = (reverse acc, [])
    collect depth acc (Tok "(" : xs) = collect (depth + 1) (Tok "(" : acc) xs
    collect depth acc (Tok ")" : xs)
        | depth == 1 = (reverse acc, xs)
        | otherwise = collect (depth - 1) (Tok ")" : acc) xs
    collect depth acc (x:xs) = collect depth (x:acc) xs

-- Map identifiers to rule names / token rules / literals

mapIdents :: Map.Map String String -> Map.Map String String -> [Tok] -> ([Tok], Set.Set String)
mapIdents ruleMap literalMap = foldr step ([], Set.empty)
  where
    step (Tok t) (acc, used)
        | isQuoted t = (Tok t : acc, used)
        | t == "|" || t == "*" || t == "+" || t == "?" || t == "(" || t == ")" = (Tok t : acc, used)
        | t == "." = (Tok t : acc, used)
        | Map.member t ruleMap = (Tok (ruleMap Map.! t) : acc, used)
        | Map.member t literalMap = (Tok (quoteLiteral (literalMap Map.! t)) : acc, used)
        | isTokenName t =
            let rule = "tok-" ++ toGbnfName t
            in (Tok rule : acc, Set.insert t used)
        | otherwise = (Tok t : acc, used)

    isQuoted s = not (null s) && head s == '"'

    quoteLiteral s = '"' : escape s ++ "\""

    isTokenName s = all (\c -> isAlphaNum c || c == '_') s && any isAlpha s && all (\c -> not (isAlpha c) || c == toLower c || c == '_' || c == toUpper c) s && any (`elem` ['A'..'Z']) s

renderTokens :: [Tok] -> String
renderTokens toks = fixSpacing (intercalate " " (map unTok toks))

fixSpacing :: String -> String
fixSpacing = replaceAll " (" "(" . replaceAll " )" ")" . replaceAll " *" "*" . replaceAll " +" "+" . replaceAll " ?" "?"

replaceAll :: String -> String -> String -> String
replaceAll needle repl s
    | needle == "" = s
    | otherwise = go s
  where
    go [] = []
    go str@(c:cs)
        | needle `isPrefixOf` str = repl ++ go (drop (length needle) str)
        | otherwise = c : go cs

-- -----------------------------
-- Token rules
-- -----------------------------

buildTokenRules :: Map.Map String String -> Set.Set String -> Set.Set String -> [String]
buildTokenRules literalMap allTokens usedTokens =
    let needed = Set.toList (Set.union allTokens (Set.fromList (Map.keys defaultTokenPatterns)))
        rules = concatMap (tokenRule literalMap) needed
        supportRules =
            [ "ws ::= [ \\t\\n]+"
            , "string-char ::= [^\\\"\\\\\\n] | \"\\\\\" ."
            , "string-char-sq ::= [^'\\\\\\n] | \"\\\\\" ."
            , "tok-comment ::= \"#\" [^\\n]* (\"\\n\")?"
            ]
        allRules = rules ++ supportRules
    in if null allRules then [] else "" : "# Token rules (approximations)" : allRules

tokenRule :: Map.Map String String -> String -> [String]
tokenRule literalMap name
    | otherwise =
        case Map.lookup name literalMap of
            Just lit -> ["tok-" ++ toGbnfName name ++ " ::= \"" ++ escape lit ++ "\""]
            Nothing ->
                case Map.lookup name defaultTokenPatterns of
                    Just pat -> ["tok-" ++ toGbnfName name ++ " ::= " ++ pat]
                    Nothing -> ["tok-" ++ toGbnfName name ++ " ::= [^\\n]+"]

-- Approximate token patterns

defaultTokenPatterns :: Map.Map String String
defaultTokenPatterns = Map.fromList
    [ ("NAME", "[A-Za-z_] [A-Za-z_0-9]*")
    , ("NUMBER", "\"-\"? [0-9]+ (\".\" [0-9]+)? ([eE] [+-]? [0-9]+)?")
    , ("STRING", "(\"\\\"\\\"\\\"\" string-char* \"\\\"\\\"\\\"\" | \"\\\"\" string-char* \"\\\"\" | \"'\" string-char-sq* \"'\")")
    , ("NEWLINE", "\"\\n\"")
    , ("INDENT", "[ \\t]+")
    , ("DEDENT", "[ \\t]*")
    , ("ENDMARKER", "ws*")
    , ("COMMENT", "\"#\" [^\\n]* (\"\\n\")?")
    , ("TYPE_COMMENT", "tok-comment")
    , ("TYPE_IGNORE", "tok-comment")
    , ("SOFT_KEYWORD", "tok-name")
    , ("NL", "\"\\n\"")
    , ("ERRORTOKEN", "[^\\n]?")
    , ("ENCODING", "[A-Za-z0-9._-]+")
    , ("OP", "[^\\n]+")
    , ("FSTRING_START", "\"f\" | \"F\"")
    , ("FSTRING_MIDDLE", "[^\\n\"]*")
    , ("FSTRING_END", "\"\\\"\"")
    , ("TSTRING_START", "\"f\" | \"F\"")
    , ("TSTRING_MIDDLE", "[^\\n\"]*")
    , ("TSTRING_END", "\"\\\"\"")
    ]
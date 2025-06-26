'use strict';

// ----------------------------------------------------------------------------
// Copyright (c) Jonathan Ashley <trac@ifton.co.uk> 2015-2017
// ----------------------------------------------------------------------------
//
// This file is part of the Keep Interfaces Simple plugin for Trac.
//
// This software is licensed as described in the file COPYING, which
// you should have received as part of this distribution.

// Configuration file structure is
//
// [kis2_assistant]
// <field_name>.visible = <predicate>
// <field_name>.available.<option_set_name> = <predicate>
// <field_name>.options.<option_set_name> = <option list>
// <field_name>.available.<template_name> = <predicate>
// <field_name>.template.<template_name> = <template_text>
//
// In predicates, field names evaluate to the current value of the
// corresponding field, except for the special names 'status', which evaluates
// to the ticket status, 'authname', which evaluates to the current username,
// 'true' which evaluates true and 'false', which evaluates false. If the
// field name is prefixed with an underscore, it evaluates to the value of the
// field at the time the page was loaded.
//
// Text-type fields evaluate to their contents, checkboxes evaluate to true if
// checked or false if not, and radio buttons evaluate to the selected item if
// an item is selected or undefined if no item is selected.

// Create a local namespace context named kis2...
var kis2 = (function() {

// TracInterface
//
// Field operations that depend on the structure of the Trac page are wrapped
// in methods of this facade object, for easier maintenance.
//
// Methods in the public interface:
//  attach_change_handler(trigger, callback)
//      - add function callback() to be called when trigger field is changed;
//  first_available_item()
//      - return value of first available item in a select-one or radio field;
//  initial_val()
//      - return the value of the field at the first point it was evaluated;
//  is_visible(name)
//      - return a boolean indicating whether the named item is visible;
//  select(name)
//      - select the named item and fire its 'change' trigger;
//        return true if the item exists, false otherwise;
//  selected_item()
//      - return name of the currently selected item;
//  show_field(bool, target)
//      - hide the field in the target box if the parameter is false,
//        show if true. Valid values for target are 'property' or 'ticket'. If
//        the target is omitted, defaults to 'property';
//  show_item(name, bool)
//      - hide the named item if the boolean parameter is false, show if true;
//        return true if the item exists, false otherwise;
//  trigger(event, additional_arguments?)
//      - fire the named event trigger;
//  val(new_value?)
//      - return the current value, set a new value if one is provided.
//
// Values in the public interface:
//  type - Trac field type; one of 'checkbox', 'field', 'radio' or
//  'undefined'. (Option-select fields and text fields both show up as type
//  'field'; there's never been a need to distinguish them.)
var TracInterface = function(field_name) {
    // Caches values of fields at the point they're first queried.
    if (typeof TracInterface.cache == 'undefined') {
        TracInterface.cache = {};
    }

    this.field_name = field_name;

    if (field_name == 'action') {
        // The 'action' field is a special case.
        this.selector = '[name=action][type=radio]';
        this.option_selector = this.selector;
        this.show_field = function (show) {
            return this.select_field().closest('fieldset').
                css('display', show ? '' : 'none');
        };
        this.type = 'radio';
    } else {
        this.selector = '#field-' + field_name;
        this.option_selector = '#field-' + field_name + ' option';
        this.type = 'field';
        if (this.select_field().prop('type') == 'checkbox') {
            this.type = 'checkbox';
        }
        if (this.select_field().length == 0) {
            // Radio button set.
            this.selector = '[name=field_' + field_name + ']';
            this.option_selector = this.selector;
            this.type = 'radio';
            if (this.select_field().length == 0) {
                // Header-only field (not modifiable as a change property).
                this.selector = 'td[headers=h_' + field_name + ']';
                this.option_selector = this.selector;
                this.type = 'header';
                if (this.select_field().length == 0) {
                    this.type = 'undefined';
                }
            }
        }
    }
};

TracInterface.prototype.select_field = function () {
    return $(this.selector);
}

TracInterface.prototype.select_options = function () {
    return $(this.option_selector);
}

TracInterface.prototype._options = function () {
    // Return an array containing the valid values for the element.
    if (this.type == 'checkbox') {
        return [ false, true ];
    }
    // Work around a Trac quirk: the value of empty options isn't explicitly
    // set, which means jQuery can't select the option by value.
    this.select_options().each(
        function () {
            if ($(this).val() === '') {
                $(this).val('');
            }
        });
    return this.select_options().map(function () { return this.value; }).get();
}

TracInterface.prototype._item = function (name) {
    if ($.inArray(name, this._options()) == -1) {
        return undefined;
    }
    if (this.type == 'radio') {
        var result = this.select_field().filter('[value="' + name + '"]');
    } else {
        result = $('option[value="' + name + '"]', this.select_field());
    }
    return result;
};

TracInterface.prototype.attach_change_handler = function (trigger, callback) {
    var triggering_field = new TracInterface(trigger);

    return triggering_field.select_field().on('change keyup', callback);
};

TracInterface.prototype.first_available_item = function () {
    var is_visible = function () { return this.style['display'] != 'none'; };

    if (this.type == 'radio') {
        var result = $('input', this.select_field().parent().
            filter(is_visible)).first();
    } else {
        result = this.select_field().children().filter(is_visible).first();
    }
    return result.val();
};

TracInterface.prototype.initial_val = function () {
    if (this.field_name in TracInterface.cache) {
        return TracInterface.cache[this.field_name];
    }
    return this.val();
};

TracInterface.prototype.is_visible = function (name) {
    var item = this._item(name);
    if (item === undefined) {
        return undefined;
    }

    if (this.type == 'radio') {
        var result = item.parent().css('display');
    } else {
        result = item.css('display');
    }
    return result && (result != 'none');
};

TracInterface.prototype.select = function (name) {
    var item = this._item(name);
    if (item === undefined) {
        return undefined;
    }

    if (this.type == 'radio') {
        item.checked(true);
        if (item.prop('name') == 'action') {
            item.nextAll('select').prop('disabled', false);
        }
    } else {
        item.prop('selected', true);
    }
    item.trigger('change');

    return true;
};

TracInterface.prototype.selected_item = function () {
    if (this.type == 'radio') {
        var result = this.select_field().filter(':checked');
    } else {
        result = $(':checked', this.select_field());
    }
    return result.val();
};

TracInterface.prototype.show_field = function (show, target) {
    if (target == 'ticket') {
        return $('#h_' + this.field_name).next().addBack().
               // Uncomment next line to hide change preview too...
               // add('#ticketchange .changes .trac-field-' + this.field_name).
               css('display', show ? '' : 'none');
    } else {
        return this.select_field().closest('td').prev().addBack().
            css('display', show ? '' : 'none');
    }
};

TracInterface.prototype.show_item = function (name, show) {
    var item = this._item(name);
    if (item === undefined) {
        return false;
    }

    if (this.type == 'radio') {
        item = item.parent();
    }
    item.css('display', show ? '' : 'none');

    return true;
};

TracInterface.prototype.trigger = function () {
    return this.select_field().trigger.apply(this.select_field(), arguments);
};

TracInterface.prototype.val = function () {
    var context = this.select_field();
    var result;

    switch (this.type) {
        case 'checkbox':
            result = context.checked.apply(context, arguments);
            break;
        case 'radio':
            context = context.filter(':checked');
            result = context.val.apply(context, arguments);
            break;
        case 'header':
            result = context.text().trim();
            break;
        default:
            result = context.val.apply(context, arguments);
    }

    if (!(this.field_name in TracInterface.cache)) {
        TracInterface.cache[this.field_name] = result;
    }

    return result;
};

// evaluate(predicate)
//
// Top-down parser to interpret the predicates used in the trac.ini file.
//
// The grammar for the predicates is described in the plugin's help
// documentation. The function attempts to detect syntax errors in the
// predicates and log an error message to the console.
//
// Returns a Promise which is resolved when the predicate has been evaluated.
// The value of the Promise contains the following fields:
//  If resolved:
//      .value = the result of evaluating the predicate;
//      .depends = an array of names of fields required to evaluate the
//                 predicate. This allows the caller to arrange for the
//                 predicate to be re-evaluated when necessary;
//  If rejected:
//      .error = a description of any error raised during evaluation.
var evaluate = function (predicate) {
    var token_type = '';
    var token = '';
    var rest_of_input = predicate;
    var depends = [];

    // Results of config function calls are stored in the (static) cache.
    if (typeof evaluate.cache == 'undefined') {
        evaluate.cache = {};
    }

    // config_error()
    //
    // Log an error detected in the configuration file.
    function config_error(type, where) {
        var chars_parsed = predicate.length - rest_of_input.length;

        if (window.console) {
            console.log(type);
            console.log('    ' + predicate);
            console.log(
                '    ' + new Array(chars_parsed + where).join('-') + '^');
        }
    }

    // next_token()
    //
    // Matches a token at the start of 'rest_of_input', setting 'token' to the
    // token text and 'token_type' to the token type. Token types may be field
    // names, operators or strings. The matched token is removed from
    // 'rest_of_input'.
    function next_token() {
        var m;

        // Ignoring whitespace, split the input on numbers...
        m = rest_of_input.match(/^([0-9]+(?:\.[0-9]+)?)( *)(.*)/i);
        if (m) {
            token_type = 'number'; token = m[1]; rest_of_input = m[3];
            return;
        }
        // ... or on words...
        m = rest_of_input.match(/^([A-Za-z_]\w*)( *)(.*)/i);
        if (m) {
            token_type = 'field name'; token = m[1]; rest_of_input = m[3];
            return;
        }
        // ... or on one of the various operators...
        m = rest_of_input.match(/^(,|\|\||\(|\)|&&|==|!=|~=|in|!|\+|-|\*|\/|<|>|<=|>=|\?|:)( *)(.*)/i);
        if (m) {
            token_type = 'operator'; token = m[1]; rest_of_input = m[3];
            return;
        }
        // ... or on strings delimited by single quotes.
        m = rest_of_input.match(/^'([^']*)'( *)(.*)/);
        if (m) {
            token_type = 'string'; token = m[1]; rest_of_input = m[3];
            return;
        }

        if (rest_of_input) {
            // No need to call config_error(); the error will be picked up
            // elsewhere in the parser and logged then.
            console.log('lexical error');
        }
        token_type = 'EOF'; token = '';
    }

    function term() { return new Promise(function (resolve, reject) {

        function query_server(config_func, args) {
            return new Promise(function (resolve, reject) {
                $.ajax('2kis_function', {
                    data: {
                        op: 'call_function',
                        id: page_info['id'],
                        config_func: config_func,
                        args: args
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        if (errorThrown == 'Internal Server Error') {
                            $('body').replaceWith(jqXHR.responseText);
                        }
                        reject({ error: errorThrown });
                    },
                    success: function (result) {
                        resolve({ value: result });
                    },
                    timeout: 10000
                });
            });
        }

        var result = { value: undefined };

        if (token_type == 'number') {
            // term ::= <number>
            result.value = eval(token);
            next_token();
            resolve(result);
        } else
        if (token_type == 'string') {
            // term ::= '"' <string> '"'
            result.value = token;
            next_token();
            resolve(result);
        } else
        if (token == '(') {
            // term ::= '(' expression ')'
            next_token();
            resolve(expression().then(function (r) {
                if (token != ')') {
                    config_error('expected ")"', 0);
                    r.error = 'syntax error';
                    return Promise.reject(r);
                }
                next_token();
                return r;
            }));
        } else
        if (token_type != 'field name') {
            config_error('unexpected token', 0);
            result.error = 'syntax error';
            reject(result);
            return;
        } else
        // term ::= <field_value>
        if (token[0] == '_') {
            var field = new TracInterface(token.slice(1));
            result.value = field.initial_val();
            next_token();
        } else
        if (token == 'status') {
            // Can't use $('.trac-status a').text(), because that would
            // fail if previewing a transition to the next state.
            result.value = page_info['status'];
            next_token();
        } else
        if (token == 'authname') {
            result.value = page_info['authname'];
            next_token();
        } else
        if (token == 'true' || token == 'false') {
            result.value = eval(token);
            next_token();
        } else {
            var field = new TracInterface(token);
            result.value = field.val();
            if (field.type !== 'undefined') {
                // If the field is not yet listed as a dependency for this
                // predicate, add it now.
                if ($.inArray(token, depends) == -1) {
                    depends.push(token);
                }
            }

            var term_token = token;
            next_token();

            if (token == '(') {
                next_token();
                result = param_list().then(function (r) {
                    if (token != ')') {
                        config_error('expected ")"', 0);
                        r.error = 'syntax error';
                        return Promise.reject(r);
                    }
                    next_token();
                    var cache_key = term_token + '@' + r.value.join();
                    if (!(cache_key in evaluate.cache)) {
                        evaluate.cache[cache_key] = query_server(
                            term_token,
                            r.value
                        );
                    }
                    return evaluate.cache[cache_key].then(function (c) {
                        r.value = c.value;
                        return r;
                    });
                });
            } else {
                if (field.type === 'undefined') {
                    console.log('no field named ' + field.field_name
                                + ' present on page');
                    result.error = 'undefined field ' + field.field_name;
                    reject(result);
                }
            }
        }
        resolve(result);
    });}

    function membership() {
        return term().then(function (t) {
            if (token == 'in') {
                next_token();
                return cmp_list().then(function (c) {
                    c.value = ($.inArray(t.value, c.value) != -1);
                    return c;
                });
            } else
            return t;
       });
    }

    function param_list() {
        if (token == ')') {
            return Promise.resolve({ value: [] });
        } else {
            return expression().then(function (r) {
                if (token == ',') {
                    next_token();
                    return param_list().then(function (p) {
                        p.value = [r.value].concat(p.value);
                        return p;
                    });
                } else {
                    r.value = [r.value];
                    return r;
                }
            });
        }
    }

    function cmp_list() {
        if (token == '(') {
            // cmp_list ::= '(' cmp_list ')'
            next_token();
            return cmp_list().then(function (r) {
                if (token != ')') {
                    config_error('expected ")"', 1);
                    r.error = 'syntax error';
                    return Promise.reject(r);
                }
                next_token();
                return r;
            });
        } else {
            // cmp_list ::= expression
            return expression().then(function (r) {
                if (token == ',') {
                    // cmp_list ::= expression ',' cmp_list
                    next_token();
                    return cmp_list().then(function (c) {
                        c.value = [r.value].concat(c.value);
                        return c;
                    });
                } else {
                    r.value = [r.value];
                    return r;
                }
            });
        }
    }

    function negation() {
        if (token == '-') {
            // negation ::= '-' negation
            next_token();
            return negation().then(function (n) {
                n.value = -n.value;
                return n;
            });
        } else
        if (token == '!') {
            // negation ::= '!' negation
            next_token();
            return negation().then(function (n) {
                n.value = !n.value;
                return n;
            });
        } else
        return membership();
    }

    function product() {
        // product ::= negation
        return negation().then(function (r) {
            if ((token == '*') || (token == '/')) {
                // product ::= negation '*' | '/' product
                var op = token;
                next_token();
                return product().then(function (p) {
                    if (op == '*') {
                        p.value = r.value * p.value;
                    } else {
                        p.value = r.value / p.value;
                    }
                    return p;
                });
            } else {
                return r;
            }
        });
    }

    function sum() {
        // sum ::= product
        return product().then(function (r) {
            if ((token == '+') || (token == '-')) {
                // sum ::= product '+' | '-' sum
                var op = token;
                next_token();
                return sum().then(function (s) {
                    if (op == '+') {
                        s.value = r.value + s.value;
                    } else {
                        s.value = r.value - s.value;
                    }
                    return s;
                });
            } else {
                return r;
            }
        });
    }

    function comparison() {
        // comparison ::= sum
        return sum().then(function (r) {
            if ((token == '<') || (token == '>') || (token == '<=') ||
                    (token == '>=')) {
                // comparison ::= sum '<' | '>' | '<=' | '>=' comparison
                var op = token;
                next_token();
                return comparison().then(function (c) {
                    if (op == '<') {
                        c.value = r.value < c.value;
                    } else if (op == '>') {
                        c.value = r.value > c.value;
                    } else if (op == '<=') {
                        c.value = r.value <= c.value;
                    } else { // op == '>='
                        c.value = r.value >= c.value;
                    }
                    return c;
                });
            } else {
                return r;
            }
        });
    }

    function equality() {
        // equality ::= comparison
        return comparison().then(function (r) {
           if (token == '==') {
                // equality ::= comparison '==' equality
                next_token();
                return equality().then(function (t) {
                    t.value = (r.value == t.value);
                    return t;
                });
            } else
            if (token == '!=') {
                // equality ::= comparison '!=' equality
                next_token();
                return equality().then(function (t) {
                    t.value = (r.value != t.value);
                    return t;
                });
            } else
            if (token == '~=') {
                // equality ::= comparison '~=' equality
                next_token();
                return equality().then(function (t) {
                    if (typeof(r.value) != 'string') {
                        config_error('match against non-string', 0);
                        r.error = 'type error (check operator precedence)';
                        return Promise.reject(r);
                    }
                    t.value = Boolean(r.value.match(t.value));
                    return t;
                });
            } else {
                return r;
            }
        });
    }

    function and_expression() {
        // and_expression ::= sum
        return equality().then(function (r) {
            if (token == '&&') {
                // and_expression ::= sum '&&' and_expression
                next_token();
                return and_expression().then(function (a) {
                    a.value = r.value && a.value;
                    return a
                });
            } else {
                return r;
            }
        });
    }

    function or_expression() {
        return and_expression().then(function (r) {
            if (token == '||') {
                // or_expression ::= and_expression '||' or_expression
                next_token();
                return or_expression().then(function (e) {
                    e.value = r.value || e.value;
                    return e;
                });
            } else {
                return r;
            }
        });
    }

    function expression() {
        // expression ::= or_expression()
        return or_expression().then(function (r) {
            if (token == '?') {
                // expression ::= or_expression '?' expression ':' expression
                next_token();
                return expression().then(function (e_true) {
                    if (token != ':') {
                        r.error = 'syntax error';
                        return Promise.reject(r);
                    }
                    next_token();
                    return expression().then(function (e_false) {
                        if (r.value) {
                            return e_true;
                        } else {
                            return e_false;
                        }
                    });
                });
            } else {
                return r;
            }
        });
    }

    next_token();

    return expression().then(function (r) {
        if (token) {
            config_error('unexpected input', -token.length + 1);
            r.error = 'syntax error';
            return Promise.reject(r);
        } else {
            r.depends = depends;
            return r;
        }
    });
}

// Field()
//
// Class-like object, instances of which are used to manage each field.
//
// Uses each field's settings in the trac.ini file to determine the
// conditions under which its visibility should change, or its available
// option-sets should be updated. Attaches handlers to every other field
// that has an affect on this field to re-evaluate these conditions as
// required.
var Field = function (field_name) {
    this.field_name = field_name;
    this.operations = page_info['trac_ini'][field_name];
    this.ui = new TracInterface(field_name);

    // Flags to ensure visibility, option-select and template onchange
    // handlers are only attached once.
    this.options_onchange_attached = false;
    this.template_onchange_attached = false;
    this.update_onchange_attached = false;
    this.visibility_onchange_attached = [];
    this.visibility_onchange_attached['property'] = false;
    this.visibility_onchange_attached['ticket'] = false;
}

// set_options()
//
// Sets up an option-select field. Called at setup time and later as an
// onchange handler of any field that might affect the contents of this field.
Field.prototype.set_options = function () {
    var callback = this.set_options.bind(this);

    // Resolve all the evaluations up-front. Create two arrays indexed by the
    // set name. all_set_items['set_name'] is a list of the items in that set.
    // all_set_show['set_name'] is the evaluated predicate for whether the
    // items in that set should be visible.
    var all_set_items = [];
    var all_set_show = [];
    var promise_list = [];
    for (var option_set in this.operations['options']) {
        var set_show = function(option_set) {
            return function (o) {
                all_set_show[option_set] = o;
            }
        };
        var set_items = function (option_set) {
            return function (o) {
                all_set_items[option_set].push(o.value);
            }
        };
        var option_values = this.operations['options'][option_set]['#'];
        var option_available =
            this.operations['available'][option_set]['#'].join(', ');
        promise_list.push(
            evaluate(option_available).then(set_show(option_set))
        );
        all_set_items[option_set] = [];
        for (var option_value in option_values) {
            promise_list.push(
                evaluate(option_values[option_value]).then(
                    set_items(option_set)
                )
            );
        }
    }
    return Promise.all(promise_list).then(function (unused) {
        // Hide all the options that are controlled by KISplugin.
        for (var option_set in all_set_items) {
            for (var option in all_set_items[option_set]) {
                var option_field = all_set_items[option_set][option];
                if (!this.ui.show_item(option_field, false)) {
                    if (this.field_name != 'action') {
                        // Log a warning: that value isn't present. (This
                        // isn't true for actions, which aren't always
                        // available in the interface.)
                        console.log("option '" + this.field_name + "' value '"
                            + option_field + "' not defined in trac.ini");
                    }
                }
            }
        }
        // Unhide all the options that are to be shown.
        for (var option_set in all_set_show) {
            if (all_set_show[option_set].value === true) {
                for (var option in all_set_items[option_set]) {
                    this.ui.show_item(all_set_items[option_set][option], true);
                }
            }
        }
        // Ensure that a visible option is selected, if necessary and
        // possible.
        if (!this.ui.is_visible(this.ui.selected_item())) {
            // Use the original value at page-load if available.
            if (this.ui.is_visible(this.ui.initial_val())) {
                this.ui.select(this.ui.initial_val());
            } else {
                this.ui.select(this.ui.first_available_item());
            }
        }

        if (!this.options_onchange_attached) {
            // Attach the onchange handlers.
            var attached_triggers = [];
            for (var option_set in all_set_show) {
                var trigger_set = all_set_show[option_set].depends;
                for (var triggers_index in trigger_set) {
                    var trigger = trigger_set[triggers_index];
                    if ($.inArray(trigger, attached_triggers) == -1) {
                        this.ui.attach_change_handler(trigger, callback);
                        attached_triggers.push(trigger);
                    }
                }
                this.options_onchange_attached = true;
            }
        }
        return unused;
    }.bind(this)).caught(function (err) {
        console.log(this.field_name + '.available ' + err.error);
        return err;
    }.bind(this));
};

// set_update()
//
// Updates the value of a feld. Called at setup time and as an onchange
// handler of any field that affects whether the value of this field should be
// changed.
Field.prototype.set_update = function () {
    var update = this.operations['update']['#'].join(', ');
    var update_when = ('when' in this.operations['update']) ?
        this.operations['update']['when']['#'].join(', ') : null;

    function attach_update_handlers(change) {
        // Attach the onchange handlers.
        for (var triggers_index in change.depends) {
            var trigger = change.depends[triggers_index];
            this.ui.attach_change_handler(
                trigger,
                this.set_update.bind(this)
            );
        }
        this.update_onchange_attached = true;
        return change;
    }

    function attach_update_error(result) {
        console.log(this.field_name + '.update.when ' + result.error);
        return result;
    }

    function update_success(change) {
        // Only allow boolean 'false' to be assigned to checkboxes. For other
        // types of fields, we assume that isn't what's wanted and leave the
        // field unchanged.
        if ((change.value !== false) || this.ui.type == 'checkbox') {
            if (this.val() != change.value) {
                // Send notification that the field content has changed.
                this.val(change.value);
                this.ui.trigger('change');
            }
        }
        return change;
    }

    function update_failure(result) {
        console.log(this.field_name + '.update ' + result.error);
        return result;
    }

    if (!this.update_onchange_attached) {
        if (update_when) {
            return evaluate(update_when).then(
                attach_update_handlers.bind(this),
                attach_update_error.bind(this)
            ).then(
                function (change) {
                    // FIXME this line can throw an error 'change undefined'.
                    if (change.value) {
                        return evaluate(update).then(
                            update_success.bind(this),
                            update_failure.bind(this)
                        );
                    } else {
                        return change;
                    }
                }.bind(this)
            );
        } else {
            return evaluate(update).then(
                attach_update_handlers.bind(this),
                attach_update_error.bind(this)
            ).then(
                update_success.bind(this),
                update_failure.bind(this)
            );
        }
    }

    if (update_when) {
        return evaluate(update_when).then(function (change) {
            if (change.value) {
                return evaluate(update).then(
                    update_success.bind(this),
                    update_failure.bind(this)
                );
            } else {
                return change;
            }
        }.bind(this));
    } else {
        return evaluate(update).then(
            update_success.bind(this),
            update_failure.bind(this)
        );
    }
}

// set_template()
//
// Applies a template to a field. Called at setup time and as an onchange
// handler of any field that affects whether the template should be applied.
// Templates are only applied to fields that are either blank, or contain an
// unmodified template.
Field.prototype.set_template = function () {
    var matches_a_template = function () {
        // Returns a Promise that resolves True if the current content of the
        // field matches any of the templates defined for the field, False
        // otherwise.
        var templates = [];
        for (var template in this.operations['template']) {
            var content = this.operations['template'][template]['#'].join(', ');
            templates.push(evaluate(content).then(function (c) {
                return this.val().replace(/[ \n]/g, '') ==
                    c.value.replace(/\\n/g, '\n').replace(/[ \n]/g, '');
            }.bind(this)));
        }
        return Promise.all(templates).then(function (t) {
            return $.inArray(true, t) != -1;
        });
    }.bind(this);

    var predicates = [];
    var template_triggers = [];
    for (var template in this.operations['available']) {

        var success = function(template, field) { return function (result) {
            for (var dependency in result.depends) {
                var trigger = result.depends[dependency];
                if ($.inArray(trigger, template_triggers) == -1) {
                    template_triggers.push(trigger);
                }
            }
            if (result.value) {
                // Apply template if field is empty or matches a template
                // value.
                matches_a_template().then(function (matched) {
                    var content =
                        field.operations['template'][template]['#'].join(', ');
                    evaluate(content).then(function (c) {
                        if (field.val() == '' || matched) {
                            field.val(c.value.replace(/\\n/g, '\n'));
                            // Notify other scripts that the field content has
                            // changed.
                            field.ui.trigger('onpaste');
                        }
                    });
                });
            }
            return result;
        } }

        var predicate = this.operations['available'][template]['#'].join(', ');
        predicates.push(evaluate(predicate).then(success(template, this)));
    }

    return Promise.all(predicates).then(function (p) {
        if (!this.template_onchange_attached) {
            // Attach the onchange handlers.
            for (var triggers_index in template_triggers) {
                var trigger = template_triggers[triggers_index];
                this.ui.attach_change_handler(
                    trigger,
                    this.set_template.bind(this)
                );
            }
            this.template_onchange_attached = true;
        }
        return p;
    }.bind(this)).caught(function (p) {
        console.log(this.field_name + '.available ' + p.error);
        return p;
    }.bind(this));
};

// set_field_visibility(target)
//
// Sets the visibility of a field or an action in the Change Properties box or
// in the ticket box.
// Called at setup time, then registered as an onchange handler of any field
// that might affect the contents of this field.
Field.prototype.set_field_visibility = function (target) {
    function evaluate_success(target, visibility) {
        this.ui.show_field(visibility.value, target);

        if (!this.visibility_onchange_attached[target]) {
            // Attach the onchange handlers.
            for (var triggers_index in visibility.depends) {
                var trigger = visibility.depends[triggers_index];
                this.ui.attach_change_handler(
                    trigger,
                    this.set_field_visibility.bind(this, target)
                );
            }
            this.visibility_onchange_attached[target] = true;
        }
        return visibility;
    }

    function evaluate_error(target, result) {
        console.log(this.field_name + '.visible.' + target +
                    ' ' + result.error);
        return result;
    }

    // Show or hide field according to the value of its visibility predicate.
    return evaluate(this.operations['visible'][target]['#'].join(', ')).then(
        evaluate_success.bind(this, target),
        evaluate_error.bind(this, target)
    );
};

// set_visibility()
//
// Calls set_field_visibility() with parameters set depending on whether this
// field is to have controlled visibility in the Change Properties box, the
// ticket box, or both.
Field.prototype.set_visibility = function() {
    var visibility_promises = [];
    var specific_target = false;

    for (var target in this.operations['visible']) {
        if (target == 'property') {
            visibility_promises.push(this.set_field_visibility('property'));
            specific_target = true;
        }
        else if (target == 'ticket') {
            visibility_promises.push(this.set_field_visibility('ticket'));
            specific_target = true;
        }
        else if (target == 'all') {
            this.operations['visible']['property'] = {};
            this.operations['visible']['property']['#'] = 
                this.operations['visible']['all']['#'];
            this.operations['visible']['ticket'] = {};
            this.operations['visible']['ticket']['#'] = 
                this.operations['visible']['all']['#'];
            visibility_promises.push(this.set_field_visibility('property'));
            visibility_promises.push(this.set_field_visibility('ticket'));
            specific_target = true;
        }
    }
    if (!specific_target) {
        // This field has only a bare '.visible' attribute, which is
        // interpreted as applying to the Change Properties box only. Make
        // up a '.property' attribute for it.
        this.operations['visible']['property'] = {};
        this.operations['visible']['property']['#'] = 
            this.operations['visible']['#'];
        visibility_promises.push(this.set_field_visibility('property'));
    }
    return Promise.all(visibility_promises);
};

// setup()
//
// Completely initialises a field; called exactly once for each field.
Field.prototype.setup = function () {
    var setup_promises = [];
    if (this.operations['options']) {
        setup_promises.push(this.set_options());
    }
    if (this.operations['update']) {
        setup_promises.push(this.set_update());
    }
    if (this.operations['template']) {
        setup_promises.push(this.set_template());
    }
    if (this.operations['visible']) {
        setup_promises.push(this.set_visibility());
    }
    return Promise.all(setup_promises);
}

// val()
//
// Returns or sets the Trac value of a field.
Field.prototype.val = function () {
    return this.ui.val.apply(this.ui, arguments);
};

// Page data was provided by the IRequestFilter request post-processing.
var page_info = window.kis2_page_info;

// This function is called at the time the page is initially loaded, but also
// following a preview rendering. This is needed to hide fields in the preview
// ticket box.
var ui = [];
var update_fields = function () {
    var field_promises = [];
    for(var field_name in page_info['trac_ini']) {
        var field = new Field(field_name);
        field_promises.push(field.setup().then(function (x) {
                x.field_name = this;
                return x;
            }.bind(field_name)));
        ui[field_name] = field.ui;
    }
    return Promise.all(field_promises);
};

// Trac's 'auto_preview.js' script defines a new jQuery method named
// 'autoSubmit'. This plugin needs to intercept it so that fields can be
// updated on preview, and the top of the visible window adjusted to prevent
// apparent jumping.
var hook_autoSubmit = function () {
    // This relies on auto_preview.js having registered its document-ready
    // handler first. Currently, Trac creates pages such that this is true.
    var autoSubmit = $.fn.autoSubmit;
    if (autoSubmit === undefined) {
        return;
    }
    var override_autoSubmit = function (args, update, busy) {
        var override_update = function (data, reply) {
            var offset = $(document).scrollTop() - $('#ticket').height();
            update.call(this, data, reply);
            update_fields().then(function () {
                $(document).scrollTop(offset + $('#ticket').height());
            });
        };
        autoSubmit.call(this, args, override_update, busy);
    };
    $.fn.autoSubmit = override_autoSubmit;
};

return {
    ev: evaluate,
    ui: ui,
    update_fields: update_fields,
    hook_autoSubmit: hook_autoSubmit
};

// ...close namespace.
})();

// jQuery compatibility patches.
if ($.fn.addBack === undefined) {
    $.fn.addBack = $.fn.andSelf;
}
if ($.fn.on === undefined) {
    $.fn.on = $.fn.bind;
}

// Internet Explorer v7/v8 compatibility patch.
// 'caught' is defined by Bluebird as an alias for the 'catch' method.
if (window.Promise.prototype.caught === undefined) {
    window.Promise.prototype.caught = window.Promise.prototype['catch'];
} else {
    $.fn.prop = $.fn.attr;
}

// This function is called when the page has loaded. It initialises the fields.
$(function () {
    kis2.hook_autoSubmit();
    kis2.update_fields();
});

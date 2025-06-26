jQuery(document).ready(function($) {

    /* variables */
    var sorter = $(
        '<div class="sorter">' +
        '<span class="up ui-icon ui-icon-arrowthick-1-n">↑</span>' +
        '<span class="down ui-icon ui-icon-arrowthick-1-s">↓</span></div>');
    var inputBackup = '';
    var uiOpened = false;
    var ajaxNow = false;
    var lastUpdateTime = new Date().getTime();
    var lastUpdateText = '';
    var lastRequestJson = '';
    var backup = '';
    var formToken = $('#main-form [name="__FORM_TOKEN"]').val();

    /* functions */
    function restoreDropDown(td, multi, value) {
        if ($('button', td).length === 0)
            return;
        var options = $('select option', td);
        var html = '';
        if (multi) {
            var checks = $('div ul', td)
                         .find('input[type=checkbox], input[type=radio]');
            // <select>要素には値が反映されていないので、リフレッシュする前にチェックの値を書き戻す
            // DOM操作ライクな方法で行いたかったが、innerHTMLを操作する方法以外の方法では、selected
            // 属性を変化させる事ができない。なぜ？
            html = '<select multiple="multiple">';
            for (i = 0; i < options.length; i++) {
                var name = $(options[i]).text();
                var selected = checks[i].checked ? 'selected="selected"' : '';
                html += '<option ' + selected + ' >' + $.htmlEscape(name) + '</option>';
            }
            html += '</select>';
        } else {
            html = '<select>';
            if (value === false) {
                value = $('select', td).multiselect('getChecked').val();
            }
            for (i = 0; i < options.length; i++) {
                var name = $(options[i]).text();
                var selected = name == value ? 'selected="selected"' : '';
                html += '<option ' + selected + ' >' + $.htmlEscape(name) + '</option>';
            }
            html += '</select>';
        }
        td.html(html);
    }

    function setupOperations(tr) {
        var td = $('td.col-operations', tr);
        restoreDropDown(td, true);
        var select = td.find('select');
        select.multiselect({
            header: false, selectedList: 1, close: updateChart,
            appendTo: td, position: {of: td, my: 'left top', at: 'left bottom'}});
        $('div.ui-multiselect-menu ul li label', td).append(sorter.clone());
        $('div.ui-multiselect-menu', td).css('min-width', td.css('width'));
    }

    function setupPermissions(tr) {
        var td = $('td.col-permissions', tr);
        restoreDropDown(td, true);
        $('select', td).multiselect({
            header: false, selectedList: 1, appendTo: td,
            position: {of: td, my: 'left top', at: 'left bottom'}});
        $('div.ui-multiselect-menu', td).css('min-width', td.css('width'));
        var ul = $('div.ui-multiselect-menu ul.ui-multiselect-checkboxes', td);
        var checkboxes = $('li input', ul);
        var handler = function() {
            checkboxes.each(checkboxes[0].checked ?
                            function(idx) { this.disabled = idx !== 0 } :
                            function(idx) { this.disabled = false });
        };
        handler();
        $(checkboxes[0]).click(handler);
    }

    function setupNextStatus(tr) {
        var td = $('td.col-next-status', tr);
        restoreDropDown(td, false, false);
        $('select', td).multiselect({
            header: false, selectedList: 1, multiple: false, minWidth: 120,
            close: updateChart,
            appendTo: td, position: {of: td, my: 'left top', at: 'left bottom'}});
        $('div.ui-multiselect-menu', td).css('min-width', td.css('width'));
    }

    function setupLine(tr) {
        $('td.col-action input', tr).val($('td.col-action span:first', tr).text());
        $('td.col-logname input', tr).val($('td.col-logname span:first', tr).text());
        setupOperations(tr);
        setupPermissions(tr);
        setupNextStatus(tr);
        return tr;
    }

    function closeUi() {
        $('#elements .editable input').css('display', 'none');
        $('#elements .editable a').css('display', 'none');
        $('#elements .editable span').css('display', '');
        uiOpened = false;
    }

    function swapStatus(no1, no2) {
        var el1 = $($('#status-editor-1 th')[no1]).clone(true);
        var el2 = $($('#status-editor-1 th')[no2]).clone(true);
        $($('#status-editor-1 th')[no1]).replaceWith(el2);
        $($('#status-editor-1 th')[no2]).replaceWith(el1);
        $('#elements tbody tr').each(function() {
            var el1 = $($('.col-before-status', this)[no1]).clone(true);
            var el2 = $($('.col-before-status', this)[no2]).clone(true);
            $($('.col-before-status', this)[no1]).replaceWith(el2);
            $($('.col-before-status', this)[no2]).replaceWith(el1);
            var val1 = $($('.col-next-status option', this)[no1 + 1]).text();
            var val2 = $($('.col-next-status option', this)[no2 + 1]).text();
            $($('.col-next-status option', this)[no2 + 1]).text(val1);
            $($('.col-next-status option', this)[no1 + 1]).text(val2);
            setupNextStatus(this);
        });
        updateChart();
    }

    function cols(el) {
        var elid = $(el).attr('id').split('-');
        elid.shift();
        return $('.col-' + elid.join('-'));
    }

    function selectCurrentLine(line) {
        line = $(line);
        if (line.closest('tr').hasClass('current-line')) {
            $('#elements tbody tr').removeClass('current-line');
            return;
        }
        $('#elements tbody tr').removeClass('current-line');
        line.closest('tr').addClass('current-line');
        return false;
    }

    function swapOperationOrder(obj, idx1, idx2) {
        obj = $(obj);
        var checks = $("input[type='checkbox']", obj.closest('ul'));
        var options = $('option', obj.closest('td'));

        // <select>要素には値が反映されていないので、リフレッシュする前にチェックの値を書き戻す
        // DOM操作ライクな方法で行いたかったが、innerHTMLを操作する方法以外の方法では、selected
        // 属性を変化させる事ができない。なぜ？
        var html = '';
        for (i = 0; i < checks.length; i++) {
            var name = $(options[i]).text();
            var selected = checks[i].checked ? 'selected="selected"' : '';
            html += '<option ' + selected + ' >' + $.htmlEscape(name) + '</option>';
        }
        var sel = $('select', obj.closest('td'));
        sel.html(html);
        options = $('option', sel);
        var op1 = $(options[idx1]).clone(true);
        var op2 = $(options[idx2]).clone(true);
        $(options[idx2]).replaceWith(op1);
        $(options[idx1]).replaceWith(op2);
        var td = obj.closest('td');
        $('select', td).multiselect('refresh');
        $('div.ui-multiselect-menu ul li label', td).append(sorter.clone());
        $('div.ui-multiselect-menu', td).css('min-width', td.css('width'));
    }

    function isDirty() {
        return backup != $.toJSON(createParams({mode: 'backup'}));
    }

    function resetDirtyFlag() {
        backup = $.toJSON(createParams({mode: 'backup'}));
    }

    function createParams(out) {
        out['status'] = [];
        out['actions'] = [];
        if ($('#editor-mode').val() == 'text') {
            out['text'] = $('#text-data').val();
        }
        $('#status-editor-1 th input').each(function() {
            out.status.push($(this).val());
        });
        var count = 0;
        $('#elements tbody tr').each(function() {
            var tmp = {};
            tmp['action'] = $('.col-action input', this).val();
            tmp['name'] = $('.col-logname input', this).val();

            tmp['operations'] = [];
            $('.col-operations select', this).multiselect('getChecked').each(function() {
                tmp['operations'].push($(this).val());
            });
            tmp['permissions'] = [];
            $('.col-permissions select', this).multiselect('getChecked').each(function() {
                tmp['permissions'].push($(this).val());
            });
            tmp['next'] = $('.col-next-status select', this).multiselect('getChecked').val();
            if (!tmp['next']) tmp['next'] = '*';
            tmp['default'] = 1000 - count;
            tmp['before'] = [];
            var colNo = 0;
            $('.col-before-status', this).each(function() {
                if ($(this).hasClass('status-checked')) {
                    tmp['before'].push(out.status[colNo]);
                }
                colNo++;
            });
            out.actions.push(tmp);
            count++;
        });
        return out;
    }

    function updateChart() { return _updateChart(false) }
    function updateChartForce() { return _updateChart(true) }

    function _updateChart(force) {
        function uiEnabled() {
            button.disabled = false;
            indicator.css('display', 'none');
        }
        function uiDisabled() {
            button.disabled = true;
            indicator.css('display', '');
        }

        var button = $('#chart-update-button')[0];
        var indicator = $('#chart-update-status');
        var jsonstr = $.toJSON(createParams({mode: 'update-chart'}));
        if (!force && lastRequestJson === jsonstr)
            return;
        uiDisabled();
        ajaxNow = true;
        var editor = $('#editor-mode').val();
        $.ajax({
            url:       location.href,
            type:      'POST',
            cache:     false,
            dataType:  'json',
            data:      {editor_mode: editor, params: jsonstr,
                        __FORM_TOKEN: formToken},
            success:   function(result) {
                var msg = $('#tabcontent .system-message');
                msg.hide().empty();
                if (!result['result']) {
                    var area = $('#image-area');
                    var image = $('<img>');
                    var replace = function() {
                        area.css('height', '');
                        area.find('img').replaceWith(this);
                    };
                    image.bind({load: replace, error: replace});
                    var height = area.css('height');
                    if (parseInt(height, 10) !== 0)
                        area.css('height', height);
                    image.attr('src', result.image_url);
                    uiEnabled();
                    area.show();
                } else {
                    uiEnabled();
                    var errors = $('<ul>');
                    $.each(result.errors, function(idx, val) {
                        errors.append($('<li>').text(val));
                    });
                    msg.append($('<p>').text(_("There was an error.")),
                               errors);
                    msg.show();
                }
            },
            error:     ajaxErrorFunc,
            complete:  function(XMLHttpRequest, textStatus) {
                ajaxNow = false;
                lastUpdateTime = new Date().getTime();
            }
        });
        lastRequestJson = jsonstr;
        if (editor == 'text') {
            lastUpdateText = $('#text-data').val();
        }
        return false;
    }

    function changeStatus(input) {
        var oldText = $('span:first', $(input).parent()).text();
        var newText = $(input).val();

        var others = {'*': true};
        $('#status-editor-1 th input').each(function() {
            if (this != input) {
                others[$(this).val()] = true;
            }
        });
        if (others[newText]) {
            $(input).val(oldText);
            alert(_('The status name overlaps. \nPlease specify the name not overlapping.'));
            return;
        }

        $('span:first', $(input).parent()).text(newText);
        $('#elements tbody tr').each(function() {
            curValue = $('.col-next-status select', this).multiselect('getChecked').val();
            if (curValue == oldText) curValue = newText;
            restoreDropDown($('td.col-next-status', this), true, '');
            $('.col-next-status select option').each(function() {
                if ($(this).text() == oldText) {
                    $(this).text(newText);
                }
            });
            $('.col-next-status select').val(curValue);
            setupNextStatus(this);
        });
    }

    function saveSucceeded(result) {
        var msg = $('#tabcontent .system-message');
        msg.hide().empty();
        if (!result['result']) {
            resetDirtyFlag();
            alert(_("Your changes has been saved."));
        } else {
            var errors = $('<ul>');
            $.each(result.errors, function(idx, val) {
                errors.append($('<li>').text(val));
            });
            msg.append($('<p>').text(_("There was an error.")), errors);
            msg.show();
            alert(_("There was an error."));
        }
    }

    function ajaxErrorFunc(xmlHttpRequest, textStatus, errorThrown) {
        alert(_("There was an internal error.\nresult status code=") + xmlHttpRequest.status + _("\n\n Please check log file of server."));
    }

    /* start setting */

    // 何もない所をクリックしたら、UIを閉じる
    $('body').click(function() {
        closeUi();
    });

    // 各行の初期化
    $('#elements tbody tr').each(function() {
        setupLine(this);
    });

    // 「取り得るステータス」列の初期化
    $('#elements thead th.editable').each(function() {
        $('input', this).val($('span:first', this).text());
    });

    // 表示設定の初期化
    $('#setview input').each(function() {
        if (!$(this).is(':checked')) {
            cols(this).css('display', 'none');
        }
    });

    // 表示設定の初期化
    $('#setview input').click(function() {
        if (!$(this).is(':checked')) {
            cols(this).css('display', 'none');
        } else {
            try {
                cols(this).css('display', 'table-cell');
            } catch (e) {
                cols(this).css('display', 'block');
            }
        }
    });

    // 「操作」「表示名」を編集可能に
    $('td.editable').click(function() {
        var input = $('input', this);
        if (input.css('display') != 'inline') {
            closeUi();
            var span = $('span:first', this);
            input.css({display: 'inline', 'min-width': span.width()});
            $('a', this).css('display', 'inline');
            input.focus();
            input[0].select();
            span.css('display', 'none');
            inputBackup = input.val();
            uiOpened = true;
            return false;
        }
    });

    // 取り得るステータスを編集可能に
    $('th.editable').click(function() {
        var input = $('input', this);
        if (input.css('display') != 'inline') {
            closeUi();
            var span = $('span:first', this);
            input.css({display: 'inline', 'min-width': span.width()});
            $('a', this).css('display', 'inline');
            input.focus();
            input[0].select();
            span.css('display', 'none');
            inputBackup = input.val();
            uiOpened = true;
            return false;
        }
    });
    $('th.editable a').click(function() {
        var resetText = $('input', $(this).closest('th')).val();
        $('input', $(this).closest('th')).val(inputBackup);
        $('span', $(this).closest('th')).text(resetText);
        changeStatus($('input', $(this).closest('th'))[0]);
        closeUi();
        updateChart();
        return false;
    });

    // Cancel editting
    $('#elements').delegate('.editable a', 'click', function() {
        return false;
    });
    $('#elements').delegate(
        '.editable input[type=text]', 'blur', function(event)
    {
        var self = $(this);
        var related = event.relatedTarget;
        var parent = this.parentNode;
        if (related && related.tagName === 'A' &&
            parent === related.parentNode)
        {
            var cell = self.closest('.editable');
            cell.find('input').val(inputBackup);
            cell.find('span').text(inputBackup);
        }
        else if (parent.tagName === 'TD') {
            $('span:first', parent).text(self.val());
        }
        else {
            changeStatus(this);
        }
        closeUi();
        updateChart();
    });

    // テキスト入力のキーボード処理
    $('#elements').delegate(
        '.editable input[type=text]', 'keypress', function(event)
    {
        switch (event.keyCode) {
        case 13:  // ENTER
            $(this).trigger('blur');
            return false;
        case 27:  // ESCAPE
            var self = $(this);
            // firefoxの場合、一度イベントの外に出ないと $(this).val() で値を設定できなかったので以下のようにした
            setTimeout(function() {
                var resetText = self.val();
                $(el).val(inputBackup);
                $('span', self.closest('th')).text(resetText);
                changeStatus(self[0]);
                closeUi();
                updateChart();
            }, 1);
            return false;
        }
    });

    // 選択行を「上に移動」
    $('#line-up').click(function() {
        if (!$('.current-line').length) {
            alert(_("No row selected. Please select row."));
            return false;
        }
        if ($('.current-line')[0] == $('#elements tbody tr:first').get()[0]) {
            return false;
        }
        var curEl = $('.current-line');
        var cur = curEl.clone(true);
        var prev = $('.current-line').prev().clone(true);
        setupLine(cur);
        setupLine(prev);
        curEl.prev().replaceWith(cur);
        curEl.replaceWith(prev);
        updateChart();
        return false;
    });

    // 選択行を「下に移動」
    $('#line-down').click(function() {
        if (!$('.current-line').length) {
            alert(_("No row selected. Please select row."));
            return false;
        }
        if ($('.current-line')[0] == $('#elements tbody tr:last').get()[0]) {
            return false;
        }
        var curEl = $('.current-line');
        var cur = curEl.clone(true);
        var next = $('.current-line').next().clone(true);
        setupLine(cur);
        setupLine(next);
        curEl.next().replaceWith(cur);
        curEl.replaceWith(next);
        updateChart();
        return false;
    });

    // 選択行を「削除」
    $('#line-remove').click(function() {
        if (!$('.current-line').length) {
            alert(_("No row selected. Please select row."));
            return false;
        }
        if (confirm(_("Are you sure you want to remove selected row?"))) {
            $('.current-line').remove();
        }
        updateChart();
        return false;
    });

    // 行の追加
    var newActionDialog = $('#new-action-input-dialog');
    var newActionDialogInput = newActionDialog.find('input');
    var newActionDialogOk = function() {
        newActionDialog.dialog('close');
        var actionName = newActionDialogInput.val();
        if (!actionName)
            return false;
        var newLine = $('#elements tfoot tr:first').clone(true);
        $('.col-action span', newLine).text(actionName);
        $('.col-action input', newLine).val(actionName);
        $('.col-next-status select', newLine).html('<option>*</option>');
        var numStatus = $('#status-editor-1 th').length;
        for (var i = 0; i < numStatus; i++) {
            if (i) {
                statusCol = $('.col-before-status', $('#elements tfoot tr:first')).clone(true);
                newLine.append(statusCol);
            }
            var statusName = $('span', $('#status-editor-1 th')[i]).text();
            $('.col-next-status select', newLine).append($('<option>').text(statusName));
        }
        setupLine(newLine);
        $('#elements tbody').append(newLine);
        closeUi();
        $('#elements tbody tr').removeClass('current-line');
        $('#elements tbody tr:last').addClass('current-line');
        $('#elements tbody tr:last td.col-line-select').click(function() {
            selectCurrentLine(this);
            closeUi();
            return false;
        });
        updateChart();
        return false;
    };
    var newActionDialogCancel = function() {
        newActionDialog.dialog('close');
        return false;
    };
    newActionDialog.dialog({
        bgiframe: true, autoOpen: false, width: 400, modal: true,
        buttons: [{text: 'Ok', click: newActionDialogOk},
                  {text: 'Cancel', click: newActionDialogCancel}]
    });

    $('#add-action').click(function() {
        var actionName;
        for (var no = 1; no < 100; no++) {
            var ok = true;
            actionName = 'new-action';
            if (no != 1)
                actionName += '-' + no;
            $('#elements tbody td.col-action input').each(function() {
                if ($(this).val() == actionName) {
                    ok = false;
                    return false;
                }
            });
            if (ok) break;
        }
        newActionDialogInput.val(actionName);
        newActionDialog.dialog('open');
        return false;
    });

    newActionDialogInput.focus(function() {
        this.select();
    });


    // ステータスを右に移動
    $('#elements .right-status').click(function() {
        var c = 0;
        var rowNo = -1;
        var thisEl = $(this).parent().get()[0];
        $('#status-editor-2 th').each(function() {
            if (this == thisEl) rowNo = c;
            c++;
        });
        if (rowNo + 1 != c) {
            swapStatus(rowNo, rowNo + 1);
        } else {
            alert("Last Element");
        }
        return false;
    });

    // ステータスを左に移動
    $('#elements .left-status').click(function() {
        var c = 0;
        var rowNo = -1;
        var thisEl = $(this).parent().get()[0];
        $('#status-editor-2 th').each(function() {
            if (this == thisEl) rowNo = c;
            c++;
        });
        if (rowNo != 0) {
            swapStatus(rowNo - 1, rowNo);
        } else {
            alert("First Element");
        }
        return false;
    });

    // ステータスの削除
    $('#elements .del-status').click(function() {
        var colspan = $('#status-header-bar').attr('colspan');
        colspan = parseInt(colspan || '1', 10);
        var c = 0;
        var rowNo = -1;
        var thisEl = $(this).parent().get()[0];
        $('#status-editor-2 th').each(function() {
            if (this == thisEl) rowNo = c;
            c++;
        });
        if (c == 1) {
            alert(_("Could not delete this status. One status at least is required."));
            return false;
        }

        var force = false;
        var delName = $($('#status-editor-1 th input')[rowNo]).val();
        $('#elements tbody tr td.col-next-status select').each(function() {
            if ($(this).multiselect('getChecked').val() == delName) {
                force = true;
                return false;
            }
        });
        var msg = force
                ? _("This status is in use. Are you sure you want to remove forcibly it?")
                : _("Are you sure you want to remove this status?");
        if (!confirm(msg)) {
            return false;
        }

        $($('#status-editor-1 th')[rowNo]).remove();
        $($('#status-editor-2 th')[rowNo]).remove();
        $('#elements tbody tr').each(function() {
            $($('.col-before-status', this)[rowNo]).remove();
            restoreDropDown($('.col-next-status', this), false, false);
            $($('.col-next-status select option', this)[rowNo + 1]).remove();
            setupNextStatus(this);
        });
        $('#status-header-bar').attr('colspan', colspan - 1);
        updateChart();
        return false;
    });

    // ステータスの追加
    var newStatusDialog = $('#new-status-input-dialog');
    var newStatusDialogInput = newStatusDialog.find('input');
    var newStatusDialogOk = function() {
        newStatusDialog.dialog('close');
        var colspan = $('#status-header-bar').attr('colspan');
        colspan = parseInt(colspan || '1', 10);
        var statusName = newStatusDialogInput.val();
        if (!statusName)
            return false;
        $('#status-header-bar').attr('colspan', colspan + 1);
        var el = $($('#status-editor-1 th')[0]).clone(true);
        $('input', el).val(statusName);
        $('span:first', el).text(statusName);
        $('#status-editor-1').append(el);
        el = $($('#status-editor-2 th')[0]).clone(true);
        $('#status-editor-2').append(el);
        $('#elements tbody tr').each(function() {
            var el = $($('.col-before-status', this)[0]).clone(true);
            el.addClass('status-checked');
            $(this).append(el);
            restoreDropDown($('.col-next-status', this), false, false);
            var opt = $('<option>');
            opt.text(statusName);
            $('.col-next-status select', this).append(opt);
            setupNextStatus(this);
        });
        closeUi();
        updateChart();
        return false;
    };
    var newStatusDialogCancel = function() {
        newStatusDialog.dialog('close');
        return false;
    };
    newStatusDialog.dialog({
        bgiframe: true, autoOpen: false, width: 400, modal: true,
        buttons: [{text: 'Ok', click: newStatusDialogOk},
                  {text: 'Cancel', click: newStatusDialogCancel}]
    });

    $('#elements #add-status').click(function() {
        var colspan = $('#status-header-bar').attr('colspan');
        colspan = parseInt(colspan || '1', 10);
        if (colspan >= 30) {
            alert(_("Too many statuses. Please remove unnecessary statuses."));
            return false;
        }
        var statusName;
        for (var no = 1; no < 100; no++) {
            var ok = true;
            statusName = 'new status';
            if (no != 1) statusName += ' ' + no;
            $('#elements tr#status-editor-1 input').each(function() {
                if ($(this).val() == statusName) {
                    ok = false;
                    return false;
                }
            });
            if (ok) break;
        }
        newStatusDialogInput.val(statusName);
        newStatusDialog.dialog('open');
        return false;
    });

    newStatusDialogInput.focus(function() {
        this.select();
    });

    // ステータスの移動可能、不可能の設定
    $('.col-before-status').click(function() {
        $(this).toggleClass('status-checked');
        updateChart();
    });

    // 表内のクリックは、<body>の処理をキャンセルする
    $('#elements').click(function() {
        if (uiOpened) return false;
    });

    // 行選択処理
    $('#elements tbody tr td.col-line-select').click(function() {
        selectCurrentLine(this);
        closeUi();
        return false;
    });

    // 「処理」列のソート処理
    $('#elements').delegate(
        '.col-operations div.ui-multiselect-menu div.sorter span',
        'click', function()
    {
        var span = $(this);
        var direction;
        if (span.hasClass('up'))
            direction = -1;
        else if (span.hasClass('down'))
            direction = 1;
        else
            return false;

        var lis = $('li', span.closest('ul'));
        var thisLi = span.closest('li')[0];
        var curIndex = -1;
        for (var i = 0; i < lis.length; i++) {
            if (lis[i] == thisLi) {
                curIndex = i;
                break;
            }
        }
        if (curIndex === -1)
            return false;
        if (direction === -1) {
            if (curIndex == 0) {
                return false;
            }
        }
        else {
            if (curIndex == lis.length - 1) {
                return false;
            }
        }
        swapOperationOrder(this, curIndex, curIndex + direction);
        return false;
    });

    // 「保存して完了」
    $('#submit-button').click(function() {
        var jsonstr = $.toJSON(createParams({mode: 'update'}));
        ajaxNow = true;
        $.ajax({
            url:       location.href,
            type:      "POST",
            cache:     false,
            dataType:  'json',
            data:      {editor_mode: $('#editor-mode').val(),
                        params: jsonstr, __FORM_TOKEN: formToken},
            success:   saveSucceeded,
            error:     ajaxErrorFunc,
            complete:  function(XMLHttpRequest, textStatus) { ajaxNow = false }
        });
        return false;
    });

    // 「編集内容を破棄する」
    $('#reset-button').click(function() {
        if (!confirm(_("Are you sure you want to cancel?")))
            return false;
        var jsonstr = $.toJSON({mode: 'reset'});
        $('#main-form textarea').text(jsonstr);
        $('#main-form').submit();
        return false;
    });

    // 「初期状態に戻す」
    $('#init-button').click(function() {
        if (!confirm(_("Are you sure you want to restore initial workflow?")))
            return false;
        var jsonstr = $.toJSON({mode: 'init'});
        $('#main-form textarea').text(jsonstr);
        $('#main-form').submit();
        return false;
    });

    // 「テキストモードに切り替え」
    $('#textmode-button').click(function() {
        if (isDirty() && !confirm(_(
                "Your changes have not been saved and will be discarded if " +
                "you continue. Are you sure that you want to switch to " +
                "text mode?")))
            return false;
        var jsonstr = $.toJSON({mode: 'change-textmode'});
        $('#main-form textarea').text(jsonstr);
        $('#main-form').submit();
        return false;
    });

    // 「GUIモードに切り替え」
    $('#guimode-button').click(function() {
        if (isDirty() && !confirm(_(
                "Your changes have not been saved and will be discarded if " +
                "you continue. Are you sure that you want to switch to " +
                "GUI mode?")))
            return false;
        var jsonstr = $.toJSON({mode: 'change-guimode'});
        $('#main-form textarea').text(jsonstr);
        $('#main-form').submit();
        return false;
    });

    // ダイアグラムの更新
    $('#chart-update-button').click(updateChartForce);

    // 画面初期化
    $('#table-wrapper').css('display', 'block'); // IEでは初期化に時間が掛かるので初期化後に表示するようにしている
    if ($('#image-area').length > 0)
        updateChartForce();

    // 開始時のデータを保存しておく
    resetDirtyFlag();

    // テキストモードでは一定時間で自動更新する
    if ($('#editor-mode').val() == 'text' && auto_update_interval != 0) {

        // テキスト編集時にタイマリセット
        $('#text-data').keydown(function() {
            lastUpdateTime = new Date().getTime();
        });

        setInterval(function() {
            var now = new Date().getTime();
            // 最終更新から一定時間(auto_update_interval)経過していて
            // テキストに変更がありajaxの実行中でないならダイアグラムを更新する
            if (now - lastUpdateTime > auto_update_interval &&
                lastUpdateText != $('#text-data').val() && !ajaxNow)
            {
                lastUpdateTime = new Date().getTime();
                updateChart();
            }
        }, 1000);
    }
});

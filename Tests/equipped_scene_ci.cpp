#include "Source/SKSE/EquippedSceneCore.hpp"
#include <cassert>
#include <iostream>
#include <string_view>
#include <vector>

struct Node {
    std::string_view name;
    Node* parent{};
    std::vector<Node*> children{};
};
void attach(Node& parent, Node& child) { child.parent=&parent;parent.children.push_back(&child); }
Node* find(Node* node, std::string_view name) {
    if (!node) return nullptr;
    if (node->name==name) return node;
    for(auto* child:node->children) if(auto* result=find(child,name)) return result;
    return nullptr;
}
auto graph(Node* root,bool left=false) {
    return cms::findEquippedChainGraph(root,left,find,[](Node* node){return node->parent;});
}
int main() {
    Node root{"player"},offset{"RightMeleeWeaponOffsetNode"},decoy{"CMS_ChainAnchor"};
    attach(root,offset);attach(offset,decoy);
    assert(!graph(&root).anchor); // A collision-offset clone is not a visible weapon.
    Node right{"WEAPON"},model{"CMS_ROOT"},anchor{"CMS_ChainAnchor"};
    attach(root,right);attach(right,model);attach(model,anchor);
    const auto original=graph(&root);
    assert(original.slot==&right && original.model==&model && original.anchor==&anchor);
    Node left{"SHIELD"},leftAnchor{"CMS_ChainAnchor"};
    attach(root,left);attach(left,leftAnchor); // Model root renamed by the engine.
    assert(graph(&root,true).model==&left && graph(&root,true).anchor==&leftAnchor);
    assert(graph(&root).anchor==&anchor); // Opposite hand never selected.
    Node otherScene{"first-person"};
    assert(!graph(&otherScene).anchor); // VRIK/first-person copies cannot be mixed.
    right.children.clear();
    assert(!graph(&root).anchor); // Retaining the old model does not retain ownership.
    Node replacement{"WEAPON"},replacementAnchor{"CMS_ChainAnchor"};
    right.children.push_back(&replacement);attach(replacement,replacementAnchor);
    assert(graph(&root).anchor!=original.anchor);
    assert(graph(&root).anchor==&replacementAnchor);
    assert(!graph(nullptr).anchor);
    std::cout<<"EQUIPPED_SCENE_PASS: visible slots, renamed model root, hands, skeleton replacement, detached graph\n";
}
